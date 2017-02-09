# Copyright 2014 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# -*- coding: utf-8 -*-

"""Provide a widget to record user satisfaction with course content."""

__author__ = 'John Orr (jorr@google.com)'

import os
import urlparse

import jinja2
import logging

import sendgrid
import webapp2

import appengine_config
from google.appengine.api import mail
from google.appengine.api import apiproxy_stub_map
from common import schema_fields
from common import tags
from common import users
from controllers import utils
from models import courses
from models import custom_modules
from models import data_removal
from models import data_sources
from models import models
from models import transforms
from modules.courses import lessons
from modules.rating import messages

from datetime import datetime
from datetime import timedelta

RESOURCES_PATH = '/modules/rating/resources'

# The token to namespace the XSRF token to this module
XSRF_TOKEN_NAME = 'rating'

# The "source" field to identify events recorded by this module
EVENT_SRC = 'rating-event'

TEMPLATES_DIR = os.path.join(
    appengine_config.BUNDLE_ROOT, 'modules', 'rating', 'templates')

rating_module = None

SENDGRID_API_KEY = '<SENDGRID_API_KEY_HERE>'

AE_LIVE_DATE = datetime(2016, 11, 1, 0, 0, 0, 0)

class StudentRatingProperty(models.StudentPropertyEntity):
    """Entity to store the student's current rating of each component."""

    PROPERTY_NAME = 'student-rating-property'

    @classmethod
    def load_or_default(cls, student):
        entity = cls.get(student, cls.PROPERTY_NAME)
        if entity is None:
            entity = cls.create(student, cls.PROPERTY_NAME)
            entity.value = '{}'
        return entity

    def get_rating(self, key):
        value_dict = transforms.loads(self.value)
        return value_dict.get(key)

    def set_rating(self, key, value):
        value_dict = transforms.loads(self.value)
        value_dict[key] = value
        self.value = transforms.dumps(value_dict)


class StudentRatingEvent(models.EventEntity):

    def for_export(self, transform_fn):
        model = super(StudentRatingEvent, self).for_export(transform_fn)

        data_dict = transforms.loads(model.data)
        model.data = transforms.dumps({
            'key': data_dict['key'],
            'rating': data_dict['rating'],
            'additional_comments': data_dict['additional_comments']})

        return model


class RatingHandler(utils.BaseRESTHandler):
    """REST handler for recording and displaying rating scores."""

    URL = '/rest/modules/rating'

    def _get_payload_and_student(self):
        # I18N: Message displayed to non-logged in user
        access_denied_msg = self.gettext('Access denied.')

        if not _rating__is_enabled_in_course_settings(self.app_context):
            transforms.send_json_response(self, 401, access_denied_msg, {})
            return (None, None)

        request = transforms.loads(self.request.get('request'))

        if not self.assert_xsrf_token_or_fail(request, XSRF_TOKEN_NAME, {}):
            return (None, None)

        user = users.get_current_user()
        if user is None:
            transforms.send_json_response(self, 401, access_denied_msg, {})
            return (None, None)

        student = models.Student.get_enrolled_student_by_user(user)
        if student is None:
            transforms.send_json_response(self, 401, access_denied_msg, {})
            return (None, None)

        return (transforms.loads(request.get('payload')), student)

    def get(self):
        payload, student = self._get_payload_and_student()
        if payload is None and student is None:
            return

        key = payload.get('key')
        prop = StudentRatingProperty.load_or_default(student)
        rating = prop.get_rating(key)

        payload_dict = {
            'key': key,
            'rating': rating
        }
        transforms.send_json_response(
            self, 200, None, payload_dict=payload_dict)

    def post(self):
        payload, student = self._get_payload_and_student()
        if payload is None and student is None:
            return

        key = payload.get('key')
        rating = payload.get('rating')
        additional_comments = payload.get('additional_comments')

        if rating is not None:
            prop = StudentRatingProperty.load_or_default(student)
            prop.set_rating(key, rating)
            prop.put()

        StudentRatingEvent.record(EVENT_SRC, self.get_user(), transforms.dumps({
            'key': key,
            'rating': rating,
            'additional_comments': additional_comments
        }))

        #entry point for rating adaptive encouragement
        if additional_comments and len(additional_comments.strip()) >= 10:
            self.process_feedback_with_narrative_adaptive_encouragement(student, key)
        elif additional_comments is None or len(additional_comments.strip()) == 0:
            self.process_feedback_adaptive_encouragement(student, key)

        # I18N: Message displayed when user submits written comments
        thank_you_msg = self.gettext('Thank you for your feedback.')

        transforms.send_json_response(self, 200, thank_you_msg, {})

    def process_feedback_adaptive_encouragement(self, student, lesson_key):
        additional_fields = student.additional_fields
        #check that the student in question has given permission for adaptive encouragement emails to be sent
        sm = self.strip_name_from_additional_fields(additional_fields, 'SendMail')
        if sm == 'Yes':
            user_id = student.user_id
            enrolled_on = student.enrolled_on
            email_address = self.strip_name_from_additional_fields(additional_fields, 'EmailAddress')
            name = self.strip_name_from_additional_fields(additional_fields, 'GivenName')
            ae = models.AdaptiveEncouragement.get_by_user_id(user_id)
            if ae is None:
                #send email for initial feedback, as no adaptive encouragement record exists for the student in the datastore
                ae = models.AdaptiveEncouragement._add_new(user_id, 0, 0, 1, 0, None, None, None, False, False)
                sent = self.send_feedback_ae_email(email_address, name, ae.feedback_count, lesson_key, enrolled_on)
                if sent:
                    ae.feedback_emails_sent = 1
                    ae.first_ae_email_sent_in_week = now
            else:
                now = datetime.now()
                ae.feedback_count = ae.feedback_count + 1
                if ae.first_ae_email_sent_in_week and ae.first_ae_email_sent_in_week < now-timedelta(days=7):
                    #send email based on feedback number, and if the date we first sent an email is more than a week ago. Also reset the emails sent counter and update the date to now
                    sent = self.send_feedback_ae_email(email_address, name, ae.feedback_count, lesson_key, enrolled_on)
                    if sent:
                        ae.feedback_emails_sent = 1
                        ae.lesson_emails_sent = 0
                        ae.first_ae_email_sent_in_week = now
                elif ae.first_ae_email_sent_in_week and ae.first_ae_email_sent_in_week > now-timedelta(days=7) and ae.feedback_emails_sent<4:
                    #send email if emails sent in week is less than 4
                    sent = self.send_feedback_ae_email(email_address, name, ae.feedback_count, lesson_key, enrolled_on)
                    if sent:
                        ae.feedback_emails_sent = ae.feedback_emails_sent + 1
                elif ae.first_ae_email_sent_in_week is None:
                    #no date is set for first email in week, so just send the email, and set the emails sent counters up and the date to now
                    sent = self.send_feedback_ae_email(email_address, name, ae.feedback_count, lesson_key, enrolled_on)
                    if sent:
                        ae.feedback_emails_sent = 1
                        ae.lesson_emails_sent = 0
                        ae.first_ae_email_sent_in_week = now

            ae.put()

    def process_feedback_with_narrative_adaptive_encouragement(self, student, lesson_key):
        additional_fields = student.additional_fields
        #check that the student in question has given permission for adaptive encouragement emails to be sent
        sm = self.strip_name_from_additional_fields(additional_fields, 'SendMail')
        if sm == 'Yes':
            user_id = student.user_id
            enrolled_on = student.enrolled_on
            email_address = self.strip_name_from_additional_fields(additional_fields, 'EmailAddress')
            name = self.strip_name_from_additional_fields(additional_fields, 'GivenName')
            ae = models.AdaptiveEncouragement.get_by_user_id(user_id)
            if ae is None:
                #send email for initial feedback, as no adaptive encouragement record exists for the student in the datastore
                ae = models.AdaptiveEncouragement._add_new(user_id, 0, 0, 0, 1, None, None, None, False, False)
                sent = self.send_feedback_ae_email(email_address, name, ae.feedback_with_narrative_count, lesson_key, enrolled_on, True)
                if sent:
                    ae.feedback_emails_sent = 1
                    ae.first_ae_email_sent_in_week = now
            else:
                now = datetime.now()
                ae.feedback_with_narrative_count = ae.feedback_with_narrative_count + 1
                if ae.first_ae_email_sent_in_week and ae.first_ae_email_sent_in_week < now-timedelta(days=7):
                    #send email based on feedback number, and if the date we first sent an email is more than a week ago. Also reset the emails sent counter and update the date to now
                    sent = self.send_feedback_ae_email(email_address, name, ae.feedback_with_narrative_count, lesson_key, enrolled_on, True)
                    if sent:
                        ae.feedback_emails_sent = 1
                        ae.lesson_emails_sent = 0
                        ae.first_ae_email_sent_in_week = now
                elif ae.first_ae_email_sent_in_week and ae.first_ae_email_sent_in_week > now-timedelta(days=7) and ae.feedback_emails_sent<4:
                    #send email if emails sent in week is less than 4
                    sent = self.send_feedback_ae_email(email_address, name, ae.feedback_with_narrative_count, lesson_key, enrolled_on, True)
                    if sent:
                        ae.feedback_emails_sent = ae.feedback_emails_sent + 1
                elif ae.first_ae_email_sent_in_week is None:
                    #no date is set for first email in week, so just send the email, and set the emails sent counters up and the date to now
                    sent = self.send_feedback_ae_email(email_address, name, ae.feedback_with_narrative_count, lesson_key, enrolled_on, True)
                    if sent:
                        ae.feedback_emails_sent = 1
                        ae.lesson_emails_sent = 0
                        ae.first_ae_email_sent_in_week = now

            ae.put()

    def send_feedback_ae_email(self, email_address, name, feedback_count, lesson_key, enrolled_on, has_narrative=False):
        #sendgrid generic stuff
        sent = False
        subject, body = self.get_feedback_ae_email_body(name, feedback_count, lesson_key, enrolled_on, has_narrative)
        if subject is not None and body is not None:
            #send the email!
            sg = sendgrid.SendGridClient(SENDGRID_API_KEY)
            message = sendgrid.Mail()
            message.set_subject(subject)
            message.set_html(body)
            #change the value for message.set_from to your from email address
            message.set_from('<YOUR_FROM_EMAIL_ADDRESS_HERE>')
            message.add_to(email_address)
            status, msg = sg.send(message)
            if status == 200:
                sent = True

        return sent

    def get_feedback_ae_email_body(self, name, feedback_count, lesson_key, enrolled_on, has_narrative=False):
        #work out which email body and subject line to return
        hello = 'Hello {n},<br><br>'.format(n=name)

        if has_narrative:
            if feedback_count == 1:
                text = 'Thanks very much for providing written feedback on Citizen Maths. We try to read all of it, and what learners tell us will help us improve Citizen Maths in the future. Please continue to provide it.'
            elif feedback_count == 4:
                text = 'Thanks very much for continuing to provide written feedback on Citizen Maths. As we mentioned previously we do try to read all of it, and, when we can, to act on it. Please continue to provide it.'
            else:
                return None, None
        else:
            if feedback_count == 2:
                if enrolled_on > AE_LIVE_DATE:
                    text = 'Thank you for beginning to give us feedback on Citizen Maths. By doing so you are helping us to understand the impact that Citizen Maths is having.'
                else:
                    return None, None
            elif feedback_count == 8:
                text = "Thanks for continuing to provide feedback on Citizen Maths. Whilst we don't look at every piece of feedback, we do analyse the feedback data overall. This helps us to understand the impact that Citizen Maths is having."
            else:
                fb_check = feedback_count - 8
                if fb_check % 10 == 0:
                    text = 'Thanks for continuing to provide feedback on Citizen Maths. Please continue to provide feedback. We really appreciate it.'
                else:
                    return None, None

        regards = """<br><br>Regards,<br>
                     Seb Schmoller<br>
                     For the Citizen Maths Team<br>
                     <a href='https://citizenmaths.com/' target='_blank'>https://citizenmaths.com/</a><br><br>"""

        location = "<br>Notes<br>The course page this email was sent from was <a href='https://course.citizenmaths.com{lk}' target='_blank'>https://course.citizenmaths.com{lk}</a>. You may have got further on in Citizen Maths in the period before you opened this email.".format(lk=lesson_key)

        footer = """<br><br>You've received this email because when you registered for Citizen Maths you opted to be sent occasional encouraging emails about your progress with Citizen Maths.
                    <br><br>If you would like to unsubscribe to this service, please go to your profile page at <a href='https://course.citizenmaths.com/main/student/home' target='_blank'>https://course.citizenmaths.com/main/student/home</a> and click the \"Unsubscribe from encouragement emails\" button."""

        bodylist = [hello, text, regards, location, footer]

        body = ''.join(bodylist)

        if has_narrative:
            subject = 'Citizen Maths: your written feedback'
        else:
            subject = 'A message from the Citizen Maths team'

        return subject, body

    def strip_name_from_additional_fields(self, origin, token):
        name = None
        index = origin.find(token)
        if index >= 0:
            ss = origin[index:]
            end_index = ss.find('"]')
            if end_index > 0:
                name = ss[len(token) + 4:end_index]
        return name

class RatingEventDataSource(data_sources.AbstractDbTableRestDataSource):
    """Data source to export all rating responses."""

    @classmethod
    def get_name(cls):
        return 'rating_events'

    @classmethod
    def get_title(cls):
        return 'Rating Events'

    @classmethod
    def get_entity_class(cls):
        return StudentRatingEvent

    @classmethod
    def exportable(cls):
        return True

    @classmethod
    def get_schema(cls, unused_app_context, unused_catch_and_log,
                   unused_source_context):
        reg = schema_fields.FieldRegistry('Rating Responses',
            description='Student satisfaction ratings of content')
        reg.add_property(schema_fields.SchemaField(
            'user_id', 'User ID', 'string',
            description='Student ID encrypted with a session-specific key'))
        reg.add_property(schema_fields.SchemaField(
            'recorded_on', 'Recorded On', 'datetime',
            description='Timestamp of the rating'))
        reg.add_property(schema_fields.SchemaField(
            'content_url', 'Content URL', 'string',
            description='The URL for the content being rated'))
        reg.add_property(schema_fields.SchemaField(
            'rating', 'Rating', 'string',
            description='The rating of the content'))
        reg.add_property(schema_fields.SchemaField(
            'unit_id', 'Unit ID', 'string', optional=True,
            description='The unit the content belongs to'))
        reg.add_property(schema_fields.SchemaField(
            'lesson_id', 'Lesson ID', 'string', optional=True,
            description='The lesson the content belongs to'))
        reg.add_property(schema_fields.SchemaField(
            'additional_comments', 'Additional Comments', 'string',
            optional=True,
            description='Optional extra comments provided by the student.'))
        return reg.get_json_schema_dict()['properties']

    @classmethod
    def _parse_content_url(cls, content_url):
        unit_id = None
        lesson_id = None
        url = urlparse.urlparse(content_url)
        query = urlparse.parse_qs(url.query)

        if 'unit' in query:
            unit_id = query['unit'][0]
        elif 'assessment' in query:
            # Rating is not currently shown in assessments, but may as well be
            # future-proof
            unit_id = query['assessment'][0]

        if 'lesson' in query:
            lesson_id = query['lesson'][0]

        return unit_id, lesson_id

    @classmethod
    def _postprocess_rows(cls, unused_app_context, source_context,
            unused_schema, unused_log, unused_page_number, rows):

        transform_fn = cls._build_transform_fn(source_context)
        if source_context.send_uncensored_pii_data:
            entities = [row.for_export_unsafe() for row in rows]
        else:
            entities = [row.for_export(transform_fn) for row in rows]

        data_list = []
        for entity in entities:
            entity_dict = transforms.loads(entity.data)
            content_url = entity_dict.get('key')
            unit_id, lesson_id = cls._parse_content_url(content_url)

            data_list.append({
                'user_id': entity.user_id,
                'recorded_on': entity.recorded_on.strftime(
                    transforms.ISO_8601_DATETIME_FORMAT),
                'content_url': content_url,
                'unit_id': unit_id,
                'lesson_id': lesson_id,
                'rating': str(entity_dict.get('rating')),
                'additional_comments': entity_dict.get('additional_comments'),
            })

        return data_list


def _rating__is_enabled_in_course_settings(app_context):
    env = app_context.get_environ()
    return env .get('unit', {}).get('ratings_module', {}).get('enabled')


def extra_content(app_context):
    if not _rating__is_enabled_in_course_settings(app_context):
        return None

    user = users.get_current_user()
    if user is None or (
        models.Student.get_enrolled_student_by_user(user) is None
    ):
        return None

    template_data = {
        'xsrf_token': utils.XsrfTokenManager.create_xsrf_token(XSRF_TOKEN_NAME)
    }
    template_environ = app_context.get_template_environ(
        app_context.get_current_locale(), [TEMPLATES_DIR])
    return jinja2.Markup(
        template_environ.get_template('widget.html').render(template_data))


def get_course_settings_fields(unused_course):
    return schema_fields.SchemaField(
        'unit:ratings_module:enabled', 'Show Ratings Widget', 'boolean',
        description=messages.SHOW_RATINGS_WIDGET, optional=True)


def register_module():

    def on_module_enabled():
        courses.Course.OPTIONS_SCHEMA_PROVIDERS[
            courses.Course.SCHEMA_SECTION_UNITS_AND_LESSONS
        ].append(get_course_settings_fields)
        lessons.UnitHandler.EXTRA_CONTENT.append(extra_content)
        data_sources.Registry.register(RatingEventDataSource)
        data_removal.Registry.register_indexed_by_user_id_remover(
            StudentRatingProperty.delete_by_user_id_prefix)
        data_removal.Registry.register_unindexed_entity_class(
            StudentRatingEvent)

    global_routes = [
        (os.path.join(RESOURCES_PATH, 'js', '.*'), tags.JQueryHandler),
        (os.path.join(RESOURCES_PATH, '.*'), tags.ResourcesHandler)]

    namespaced_routes = [(RatingHandler.URL, RatingHandler)]

    global rating_module  # pylint: disable=global-statement
    rating_module = custom_modules.Module(
        'Student rating widget',
        'Provide a widget to record user satisfaction with course content.',
        global_routes, namespaced_routes,
        notify_module_enabled=on_module_enabled)

    return rating_module
