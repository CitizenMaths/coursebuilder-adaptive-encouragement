# Copyright 2013 Google Inc. All Rights Reserved.
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

"""Handlers for generating various frontend pages."""

__author__ = 'Saifu Angto (saifu@google.com)'


import copy
import datetime
import re
import urllib
import urlparse
import logging

import sendgrid
import webapp2

import ast

from common import crypto
from common import jinja_utils
from common import safe_dom
from controllers import utils
from models import counters
from models import courses
from models import custom_modules
from models import models
from models import progress
from models import review as models_review
from models import roles
from models import student_work
from models import transforms
from modules.assessments import assessments
from modules.courses import unit_outline
from modules.review import domain
from tools import verify

from modules.gitkit import gitkit

from google.appengine.ext import db

from datetime import datetime
from datetime import timedelta

COURSE_EVENTS_RECEIVED = counters.PerfCounter(
    'gcb-course-events-received',
    'A number of activity/assessment events received by the server.')

COURSE_EVENTS_RECORDED = counters.PerfCounter(
    'gcb-course-events-recorded',
    'A number of activity/assessment events recorded in a datastore.')

UNIT_PAGE_TYPE = 'unit'
ACTIVITY_PAGE_TYPE = 'activity'
ASSESSMENT_PAGE_TYPE = 'assessment'
ASSESSMENT_CONFIRMATION_PAGE_TYPE = 'test_confirmation'

TAGS_THAT_TRIGGER_BLOCK_COMPLETION = ['attempt-activity']
TAGS_THAT_TRIGGER_COMPONENT_COMPLETION = ['tag-assessment']
TAGS_THAT_TRIGGER_HTML_COMPLETION = ['attempt-lesson']

SENDGRID_API_KEY = '<SENDGRID_API_KEY_HERE>'

PI_PROPORTION = 'Proportion'
PI_REPRESENTATION = 'Representation'
PI_MEASUREMENT = 'Measurement'
PI_UNCERTAINTY = 'Uncertainty'
PI_PATTERN = 'Pattern'

ML_PROPORTION = [28, 29, 30, 31, 36, 37, 38, 39, 40, 3, 4, 5, 6, 23, 24, 25, 44, 45, 46, 47, 48, 52, 53, 54, 125, 56, 57, 58]
ML_UNCERTAINTY = [74, 75, 76, 80, 81, 82, 86, 87, 88, 126]
ML_REPRESENTATION = [98, 99, 100, 101, 105, 106, 107, 111, 112, 113]
ML_PATTERN = [129, 130, 131, 135, 136, 140, 141, 142]
ML_MEASUREMENT = [146, 147, 148, 149, 153, 154, 155, 159, 160, 161, 162, 166, 167, 168, 169]

DICT_PROPORTION = {22:[28, 29, 30, 31], 34:[36, 37, 38, 39, 40], 1:[3, 4, 5, 6, 23, 24, 25], 42:[44, 45, 46, 47, 48], 50:[52, 53, 54, 125, 56, 57, 58]}
DICT_UNCERTAINTY = {72:[74, 75, 76], 78:[80, 81, 82], 84:[86, 87, 88, 126]}
DICT_REPRESENTATION = {96:[98, 99, 100, 101], 103:[105, 106, 107], 109:[111, 112, 113]}
DICT_PATTERN = {127:[129, 130, 131], 133:[135, 136], 138:[140, 141, 142]}
DICT_MEASUREMENT = {144:[146, 147, 148, 149], 151:[153, 154, 155], 157:[159, 160, 161, 162], 164:[166, 167, 168, 169]}

DICT_PROPORTION_AL = {22:[27, 28, 29, 30, 31, 32], 34:[35, 36, 37, 38, 39, 40, 41], 1:[2, 3, 4, 5, 6, 23, 24, 25, 26], 42:[43, 44, 45, 46, 47, 48, 49], 50:[52, 53, 54, 125, 56, 57, 58, 59]}
DICT_UNCERTAINTY_AL = {72:[73, 74, 75, 76, 77], 78:[79, 80, 81, 82, 83], 84:[85, 86, 87, 88, 126, 90]}
DICT_REPRESENTATION_AL = {96:[97, 98, 99, 100, 101, 102], 103:[104, 105, 106, 107, 108], 109:[110, 111, 112, 113, 114]}
DICT_PATTERN_AL = {127:[128, 129, 130, 131, 132], 133:[134, 135, 136, 137], 138:[139, 140, 141, 142, 143]}
DICT_MEASUREMENT_AL = {144:[145, 146, 147, 148, 149, 150], 151:[152, 153, 154, 155, 156], 157:[158, 159, 160, 161, 162, 163], 164:[165, 166, 167, 168, 169, 170]}

UN_MIXING = 'Mixing'
UN_COMPARING = 'Comparing'
UN_SCALING = 'Scaling'
UN_SHARING = 'Sharing'
UN_TRADING_OFF = 'Trading off'
UN_MAKING_DECISIONS = 'Making decisions'
UN_PLAYING = 'Playing'
UN_SIMULATING = 'Simulating'
UN_INTERPRETING_DATA = 'Interpreting data'
UN_INTERPRETING_CHARTS = 'Interpreting charts'
UN_COMPARING_GROUPS = 'Comparing groups'
UN_APPRECIATING = 'Appreciating'
UN_TILING = 'Tiling'
UN_CONSTRUCTING = 'Constructing'
UN_READING_SCALES = 'Reading scales'
UN_CONVERTING = 'Converting'
UN_ESTIMATING = 'Estimating'
UN_QUANTIFYING = 'Quantifying'

UN_NO_MIXING = 'Unit 1'
UN_NO_COMPARING = 'Unit 2'
UN_NO_SCALING = 'Unit 3'
UN_NO_SHARING = 'Unit 4'
UN_NO_TRADING_OFF = 'Unit 5'
UN_NO_MAKING_DECISIONS = 'Unit 6'
UN_NO_PLAYING = 'Unit 7'
UN_NO_SIMULATING = 'Unit 8'
UN_NO_INTERPRETING_DATA = 'Unit 9'
UN_NO_INTERPRETING_CHARTS = 'Unit 10'
UN_NO_COMPARING_GROUPS = 'Unit 11'
UN_NO_APPRECIATING = 'Unit 12'
UN_NO_TILING = 'Unit 13'
UN_NO_CONSTRUCTING = 'Unit 14'
UN_NO_READING_SCALES = 'Unit 15'
UN_NO_CONVERTING = 'Unit 16'
UN_NO_ESTIMATING = 'Unit 17'
UN_NO_QUANTIFYING = 'Unit 18'

ML_MIXING = [28, 29, 30, 31]
ML_COMPARING = [36, 37, 38, 39, 40]
ML_SCALING = [3, 4, 5, 6, 23, 24, 25]
ML_SHARING = [44, 45, 46, 47, 48]
ML_TRADING_OFF = [52, 53, 54, 125, 56, 57, 58]
ML_MAKING_DECISIONS = [74, 75, 76]
ML_PLAYING = [80, 81, 82]
ML_SIMULATING = [86, 87, 88, 126]
ML_INTERPRETING_DATA = [98, 99, 100, 101]
ML_INTERPRETING_CHARTS = [105, 106, 107]
ML_COMPARING_GROUPS = [111, 112, 113]
ML_APPRECIATING = [129, 130, 131]
ML_TILING = [135, 136]
ML_CONSTRUCTING = [140, 141, 142]
ML_READING_SCALES = [146, 147, 148, 149]
ML_CONVERTING = [153, 154, 155]
ML_ESTIMATING = [159, 160, 161, 162]
ML_QUANTIFYING = [166, 167, 168, 169]

DICT_MIXING = {22:[28, 29, 30, 31]}
DICT_COMPARING = {34:[36, 37, 38, 39, 40]}
DICT_SCALING = {1:[3, 4, 5, 6, 23, 24, 25]}
DICT_SHARING = {42:[44, 45, 46, 47, 48]}
DICT_TRADING_OFF = {50:[52, 53, 54, 125, 56, 57, 58]}
DICT_MAKING_DECISIONS = {72:[74, 75, 76]}
DICT_PLAYING = {78:[80, 81, 82]}
DICT_SIMULATING = {84:[86, 87, 88, 126]}
DICT_INTERPRETING_DATA = {96:[98, 99, 100, 101]}
DICT_INTERPRETING_CHARTS = {103:[105, 106, 107]}
DICT_COMPARING_GROUPS = {109:[111, 112, 113]}
DICT_APPRECIATING = {127:[129, 130, 131]}
DICT_TILING = {133:[135, 136]}
DICT_CONSTRUCTING = {138:[140, 141, 142]}
DICT_READING_SCALES = {144:[146, 147, 148, 149]}
DICT_CONVERTING = {151:[153, 154, 155]}
DICT_ESTIMATING = {157:[159, 160, 161, 162]}
DICT_QUANTIFYING = {164:[166, 167, 168, 169]}

EOCQ_ASSESSMENT_ID = 176

LOGIC_PI_STARTED = 0
LOGIC_UC = 1
LOGIC_PI_COMPLETED = 2

INACTIVE_EMAIL_SUBJECT = "A message from the Citizen Maths team"
INACTIVE_SEVEN_DAYS_EMAIL_TEXT = """We noticed that in the week since you signed up for Citizen Maths, you seem not to have got started with the course.
                                    <br><br>We'd encourage you to make a start. If you do so, you can do as much or as little as you like in session.
                                    <br><br>In case of difficulty, feel free to get in touch and we will do what we can to help."""
INACTIVE_TWO_WEEKS_EMAIL_TEXT = """We noticed that it is two weeks since you last logged into Citizen Maths.
                                   <br><br>We hope very much that you will give Citizen Maths another try. 
                                   <br><br>In case of difficulty, feel free to get in touch and we will do what we can to help."""

def _get_first_lesson(handler, unit_id):
    """Returns the first lesson in the unit."""
    lessons = handler.get_course().get_lessons(unit_id)
    return lessons[0] if lessons else None


def _get_selected_unit_or_first_unit(handler):
    # Finds unit requested or a first unit in the course.
    u = handler.request.get('unit')
    unit = handler.get_course().find_unit_by_id(u)
    if not unit:
        units = handler.get_course().get_units()
        for current_unit in units:
            if verify.UNIT_TYPE_UNIT == current_unit.type:
                unit = current_unit
                break
    return unit


def _get_selected_or_first_lesson(handler, unit):
    # Find lesson requested or a first lesson in the unit.
    l = handler.request.get('lesson')
    lesson = None
    if not l:
        lesson = _get_first_lesson(handler, unit.unit_id)
    else:
        lesson = handler.get_course().find_lesson_by_id(unit, l)
    return lesson


def extract_unit_and_lesson(handler):
    """Loads unit and lesson specified in the request."""

    unit = _get_selected_unit_or_first_unit(handler)
    if not unit:
        return None, None
    return unit, _get_selected_or_first_lesson(handler, unit)


def get_unit_and_lesson_id_from_url(handler, url):
    """Extracts unit and lesson ids from a URL."""
    url_components = urlparse.urlparse(url)
    query_dict = urlparse.parse_qs(url_components.query)

    if 'unit' not in query_dict:
        return None, None

    unit_id = query_dict['unit'][0]

    lesson_id = None
    if 'lesson' in query_dict:
        lesson_id = query_dict['lesson'][0]
    else:
        lesson_id = _get_first_lesson(handler, unit_id).lesson_id

    return unit_id, lesson_id


class CourseHandler(utils.BaseHandler):
    """Handler for generating course page."""

    @classmethod
    def get_child_routes(cls):
        """Add child handlers for REST."""
        return [('/rest/events', EventsRESTHandler)]

    def get_user_student_profile(self):
        user = self.personalize_page_and_get_user()
        if user is None:
            student = utils.TRANSIENT_STUDENT
            profile = None
        else:
            student = models.Student.get_enrolled_student_by_user(user)
            profile = models.StudentProfileDAO.get_profile_by_user(user)
            self.template_value['has_global_profile'] = profile is not None
            if not student:
                student = utils.TRANSIENT_STUDENT
        return user, student, profile

    def get(self):
        """Handles GET requests."""
        models.MemcacheManager.begin_readonly()
        try:
            user, student, profile = self.get_user_student_profile()

            # If we are on this page due to visiting the course base URL
            # (and not base url plus "/course"), redirect registered students
            # to the last page they were looking at.
            last_location = self.get_redirect_location(student)
            if last_location:
                self.redirect(last_location)
                return

            course = self.get_course()
            course_availability = course.get_course_availability()
            settings = self.app_context.get_environ()
            self._set_show_registration_settings(settings, student, profile,
                                                 course_availability)
            self._set_show_image_or_video(settings)
            self.set_common_values(settings, student, course,
                                    course_availability)
        finally:
            models.MemcacheManager.end_readonly()
        self.render('course.html')

    def _set_show_image_or_video(self, settings):
        show_image_or_video = unicode(
            settings['course'].get('main_image', {}).get('url'))
        if show_image_or_video:
            if re.search(r'//(www\.youtube\.com|youtu\.be)/',
                         show_image_or_video):
                self.template_value['show_video'] = True
            else:
                self.template_value['show_image'] = True

    def _set_show_registration_settings(self, settings, student, profile,
                                        course_availability):
        if (roles.Roles.is_course_admin(self.app_context) or
            course_availability in (
                courses.COURSE_AVAILABILITY_REGISTRATION_REQUIRED,
                courses.COURSE_AVAILABILITY_REGISTRATION_OPTIONAL)):
            self.template_value['show_registration_page'] = True

        if not student or student.is_transient and profile:
            additional_registration_fields = self.app_context.get_environ(
                )['reg_form']['additional_registration_fields']
            if profile is not None and not additional_registration_fields:
                self.template_value['show_registration_page'] = False
                self.template_value['register_xsrf_token'] = (
                    crypto.XsrfTokenManager.create_xsrf_token('register-post'))

    def set_common_values(self, settings, student, course,
                           course_availability):
        self.template_value['transient_student'] = student.is_transient
        self.template_value['navbar'] = {'course': True}
        student_view = unit_outline.StudentCourseView(course, student, None, False)
        self.template_value['course_outline'] = student_view.contents
        self.template_value['course_availability'] = course_availability
        self.template_value['show_lessons_in_syllabus'] = (
            settings['course'].get('show_lessons_in_syllabus', False))

class UnitHandler(utils.BaseHandler):
    """Handler for generating unit page."""

    # A list of callback functions which modules can use to add extra content
    # panels at the bottom of the page. Each function receives the app_context
    # as its single arg, and should return a string or None.
    EXTRA_CONTENT = []

    # The lesson title provider should be a function which receives the
    # app_context, the unit, and the lesson, and returns a jinja2.Markup or a
    # safe_dom object. If it returns None, the default title is used instead.
    _LESSON_TITLE_PROVIDER = None

    @classmethod
    def set_lesson_title_provider(cls, lesson_title_provider):
        if cls._LESSON_TITLE_PROVIDER:
            raise Exception('Lesson title provider already set by a module')
        cls._LESSON_TITLE_PROVIDER = lesson_title_provider

    def _default_lesson_title_provider(
            self, app_context, unused_unit, lesson, unused_student):
        return safe_dom.Template(
            self.get_template('lesson_title.html'),
            lesson=lesson,
            can_see_drafts=custom_modules.can_see_drafts(app_context),
            is_course_admin=roles.Roles.is_course_admin(app_context),
            is_read_write_course=app_context.fs.is_read_write())

    def get(self):
        """Handles GET requests."""
        models.MemcacheManager.begin_readonly()
        try:
            student = None
            user = self.personalize_page_and_get_user()
            if user:
                student = models.Student.get_enrolled_student_by_user(user)
            student = student or models.TransientStudent()

            # What unit/lesson/assessment IDs are wanted for this request?
            selected_ids = []
            #apf: set up extra variable lesson_id to use later on
            lesson_id = 0
            if 'unit' in self.request.params:
                selected_ids.append(self.request.get('unit'))
                if 'lesson' in self.request.params:
                    #set a value for lesson_id 
                    lesson_id = int(self.request.get('lesson'))
                    selected_ids.append(self.request.get('lesson'))
                elif 'assessment' in self.request.params:
                    selected_ids.append(self.request.get('assessment'))

            logging.info('lesson id:')
            logging.info(lesson_id)
            # Build up an object giving this student's view on the course.
            course = self.get_course()
            student_view = unit_outline.StudentCourseView(
                course, student, selected_ids)

            # If the location in the course selected by GET arguments is not
            # available, redirect to the course overview page.
            active_elements = student_view.get_active_elements()
            if not active_elements:
                self.redirect('/')
                return
            unit = active_elements[0].course_element
            if (not unit.show_contents_on_one_page and
                len(active_elements) < len(selected_ids)):
                self.redirect('/')
                return
            lesson = assessment = None
            if len(active_elements) > 1:
                if active_elements[1].kind == 'lesson':
                    lesson = active_elements[1].course_element
                else:
                    assessment = active_elements[1].course_element

            # Set template values for nav bar and page type.
            self.template_value['navbar'] = {'course': True}

            # Set template values for a unit and its lesson entities
            self.template_value['unit'] = unit
            self.template_value['unit_id'] = unit.unit_id

            # These attributes are needed in order to render questions (with
            # progress indicators) in the lesson body. They are used by the
            # custom component renderers in the assessment_tags module.
            self.student = student
            self.unit_id = unit.unit_id

            course_availability = course.get_course_availability()
            settings = self.app_context.get_environ()
            self.template_value['course_outline'] = student_view.contents
            self.template_value['course_availability'] = course_availability
            if (unit.show_contents_on_one_page and
                'confirmation' not in self.request.params):
                self._show_all_contents(student, unit, student_view)
            else:
                # For all-on-one-page units, the student view won't believe
                # that pre/post assessments are separate, visibile things,
                # so we must separately load the appropriate assessment.
                if (unit.show_contents_on_one_page and
                    'confirmation' in self.request.params):
                    assessment = course.find_unit_by_id(
                        self.request.get('assessment'))
                self._show_single_element(student, unit, lesson, assessment,
                                          student_view)

            for extra_content_hook in self.EXTRA_CONTENT:
                extra_content = extra_content_hook(self.app_context)
                if extra_content is not None:
                    self.template_value['display_content'].append(extra_content)

            self._set_gcb_html_element_class()

            #set the lesson id for this particular unit as the intro lesson is considered a main lesson in this instance
            if self.unit_id > 0 and self.unit_id == 50 and lesson_id == 0:
                lesson_id = 52

            #entry point into lesson/course progress adaptive encouragement code
            if self.unit_id > 0 and lesson_id > 0:
                self.process_lesson_adaptive_encouragement(student, course, self.unit_id, lesson_id)
        finally:
            models.MemcacheManager.end_readonly()
        self.render('unit.html')

    def strip_name_from_additional_fields(self, origin, token):
        name = None
        index = origin.find(token)
        if index >= 0:
            ss = origin[index:]
            end_index = ss.find('"]')
            if end_index > 0:
                name = ss[len(token) + 4:end_index]
        return name

    def process_lesson_adaptive_encouragement(self, student, course, unit_id, lesson_id):
        additional_fields = student.additional_fields
        #check that the student in question has given permission for adaptive encouragement emails to be sent
        sm = self.strip_name_from_additional_fields(additional_fields, 'SendMail')
        if sm == 'Yes':
            logging.info('sm is yes')
            user_id = student.user_id
            email_address = self.strip_name_from_additional_fields(additional_fields, 'EmailAddress')
            name = self.strip_name_from_additional_fields(additional_fields, 'GivenName')

            #process adaptive encouragement for starting a powerful idea
            subject_pis, main_text_pis, pis = self.process_started_powerful_idea(course, student, lesson_id)
            self.process_adaptive_encouragement_sending_logic(name, email_address, user_id, subject_pis, main_text_pis, unit_id, lesson_id, pis, LOGIC_PI_STARTED)

            #process adaptive encouragement for nearl completing a unit
            subject_uc, main_text_uc, uc = self.process_completed_unit(course, student, lesson_id)
            self.process_adaptive_encouragement_sending_logic(name, email_address, user_id, subject_uc, main_text_uc, unit_id, lesson_id, uc, LOGIC_UC)

            #process adaptive encouragement for nearly completing a powerful idea
            subject_pic, main_text_pic, pic = self.process_completed_powerful_idea(course, student, lesson_id)
            self.process_adaptive_encouragement_sending_logic(name, email_address, user_id, subject_pic, main_text_pic, unit_id, lesson_id, pic, LOGIC_PI_COMPLETED)

    def process_adaptive_encouragement_sending_logic(self, name, email_address, user_id, subject, main_text, unit_id, lesson_id, list_value_check, list_value_type):
        #check if we have email content. If there is none, the student has not met the criteria for sending of an adaptive encouragement email and goes no further
        if subject is not None and main_text is not None:
            #get adaptive encouragement record for the student from the datastore. If one does not exist, create one.
            ae = models.AdaptiveEncouragement.get_by_user_id(user_id)
            if ae is None:
                ae = models.AdaptiveEncouragement._add_new(user_id, 0, 0, 0, 0, None, None, None, False, False)

            #work out whether to send the adaptive encouragement email based on the type of progress it is checking for.
            #if the record has no mention of the unit/powerful idea in the relevant field, then we send the email and add the unit/powerful idea to the field.
            #if the record knows about the unit/powerful idea in the relevant field, then we do not send the email and the process stops here.
            send = True
            if list_value_type == LOGIC_PI_STARTED:
                lst = None
                if ae.pi_started_emails_sent is not None:
                    lst = ast.literal_eval(ae.pi_started_emails_sent)

                if lst is not None and list_value_check in lst:
                    send = False
                elif lst is None:
                    ae.pi_started_emails_sent = str([list_value_check])
                else:
                    ae.pi_started_emails_sent = str(lst + [list_value_check])
            elif list_value_type == LOGIC_UC:
                lst = None
                if ae.unit_completed_emails_sent is not None:
                    lst = ast.literal_eval(ae.unit_completed_emails_sent)

                if lst is not None and list_value_check in lst:
                    send = False
                elif lst is None:
                    ae.unit_completed_emails_sent = str([list_value_check])
                else:
                    ae.unit_completed_emails_sent = str(lst + [list_value_check])
            elif list_value_type == LOGIC_PI_COMPLETED:
                lst = None
                if ae.pi_completed_emails_sent is not None:
                    lst = ast.literal_eval(ae.pi_completed_emails_sent)

                if lst is not None and list_value_check in lst:
                    send = False
                elif lst is None:
                    ae.pi_completed_emails_sent = str([list_value_check])
                else:
                    ae.pi_completed_emails_sent = str(lst + [list_value_check])

            if send == True:
                logging.info('into the attempting to send part')
                #constructs the main email body
                body = self.get_ae_email_body(name, main_text, unit_id, lesson_id)

                now = datetime.now()
                if ae.first_ae_email_sent_in_week and ae.first_ae_email_sent_in_week < now-timedelta(days=7):
                    #if the date we first sent an email is more than a week ago, send the email and also reset the emails sent counters and update the date to now
                    sent = self.send_ae_email(email_address, subject, body)
                    if sent:
                        ae.lesson_emails_sent = 1
                        ae.feedback_emails_sent = 0
                        ae.first_ae_email_sent_in_week = now
                elif ae.first_ae_email_sent_in_week and ae.first_ae_email_sent_in_week > now-timedelta(days=7) and ae.lesson_emails_sent<4:
                    #send email if emails sent in week is less than 4
                    sent = self.send_ae_email(email_address, subject, body)
                    if sent:
                        ae.lesson_emails_sent = ae.lesson_emails_sent + 1
                elif ae.first_ae_email_sent_in_week is None:
                    #no date is set for first email in week, so just send the email, and set the emails sent counters up and the date to now
                    sent = self.send_ae_email(email_address, subject, body)
                    if sent:
                        ae.lesson_emails_sent = 1
                        ae.feedback_emails_sent = 0
                        ae.first_ae_email_sent_in_week = now

            ae.put()

    def process_started_powerful_idea(self, course, student, lesson_id):
        #work out which powerful idea the lesson is in, and set up the variables
        if lesson_id in ML_PROPORTION:
            pi = PI_PROPORTION
            mls = DICT_PROPORTION
        elif lesson_id in ML_UNCERTAINTY:
            pi = PI_UNCERTAINTY
            mls = DICT_UNCERTAINTY
        elif lesson_id in ML_REPRESENTATION:
            pi = PI_REPRESENTATION
            mls = DICT_REPRESENTATION
        elif lesson_id in ML_PATTERN:
            pi = PI_PATTERN
            mls = DICT_PATTERN
        elif lesson_id in ML_MEASUREMENT:
            pi = PI_MEASUREMENT
            mls = DICT_MEASUREMENT
        else:
            pi = None
            mls = None

        #check that the criteria matches and then set up the email subject and body if it does, otherwise return no values
        if pi is not None and mls is not None:
            progress_tracker = progress.UnitLessonCompletionTracker(course)
            completed, total = progress_tracker.get_number_lessons_completed_for_powerful_idea_or_unit(student, mls)
            if completed == 2:
                logging.info('pi started')
                subject, main_text = self.get_email_text_pi_started(pi)
            else:
                return None, None, None
        else:
            return None, None, None

        return subject, main_text, pi

    def process_completed_unit(self, course, student, lesson_id):
        #work out which unit the lesson is in, and set up the variables
        if lesson_id in ML_MIXING:
            un = UN_MIXING
            uno = UN_NO_MIXING
            mls = DICT_MIXING
        elif lesson_id in ML_COMPARING:
            un = UN_COMPARING
            uno = UN_NO_COMPARING
            mls = DICT_COMPARING
        elif lesson_id in ML_SCALING:
            un = UN_SCALING
            uno = UN_NO_SCALING
            mls = DICT_SCALING
        elif lesson_id in ML_SHARING:
            un = UN_SHARING
            uno = UN_NO_SHARING
            mls = DICT_SHARING
        elif lesson_id in ML_TRADING_OFF:
            un = UN_TRADING_OFF
            uno = UN_NO_TRADING_OFF
            mls = DICT_TRADING_OFF
        elif lesson_id in ML_MAKING_DECISIONS:
            un = UN_MAKING_DECISIONS
            uno = UN_NO_MAKING_DECISIONS
            mls = DICT_MAKING_DECISIONS
        elif lesson_id in ML_PLAYING:
            un = UN_PLAYING
            uno = UN_NO_PLAYING
            mls = DICT_PLAYING
        elif lesson_id in ML_SIMULATING:
            un = UN_SIMULATING
            uno = UN_NO_SIMULATING
            mls = DICT_SIMULATING
        elif lesson_id in ML_INTERPRETING_DATA:
            un = UN_INTERPRETING_DATA
            uno = UN_NO_INTERPRETING_DATA
            mls = DICT_INTERPRETING_DATA
        elif lesson_id in ML_INTERPRETING_CHARTS:
            un = UN_INTERPRETING_CHARTS
            uno = UN_NO_INTERPRETING_CHARTS
            mls = DICT_INTERPRETING_CHARTS
        elif lesson_id in ML_COMPARING_GROUPS:
            un = UN_COMPARING_GROUPS
            uno = UN_NO_COMPARING_GROUPS
            mls = DICT_COMPARING_GROUPS
        elif lesson_id in ML_APPRECIATING:
            un = UN_APPRECIATING
            uno = UN_NO_APPRECIATING
            mls = DICT_APPRECIATING
        elif lesson_id in ML_TILING:
            un = UN_TILING
            uno = UN_NO_TILING
            mls = DICT_TILING
        elif lesson_id in ML_CONSTRUCTING:
            un = UN_CONSTRUCTING
            uno = UN_NO_CONSTRUCTING
            mls = DICT_CONSTRUCTING
        elif lesson_id in ML_READING_SCALES:
            un = UN_READING_SCALES
            uno = UN_NO_READING_SCALES
            mls = DICT_READING_SCALES
        elif lesson_id in ML_CONVERTING:
            un = UN_CONVERTING
            uno = UN_NO_CONVERTING
            mls = DICT_CONVERTING
        elif lesson_id in ML_ESTIMATING:
            un = UN_ESTIMATING
            uno = UN_NO_ESTIMATING
            mls = DICT_ESTIMATING
        elif lesson_id in ML_QUANTIFYING:
            un = UN_QUANTIFYING
            uno = UN_NO_QUANTIFYING
            mls = DICT_QUANTIFYING
        else:
            un = None
            uno = None
            mls = None

        #check that the criteria matches and then set up the email subject and body if it does, otherwise return no values
        if un is not None and uno is not None and mls is not None:
            progress_tracker = progress.UnitLessonCompletionTracker(course)
            completed, total = progress_tracker.get_number_lessons_completed_for_powerful_idea_or_unit(student, mls)
            logging.info(total)
            logging.info(completed)
            if total - completed == 1:
                logging.info('unit completed')
                subject, main_text = self.get_email_text_unit_complete(un, uno)
            else:
                return None, None, None
        else:
            return None, None, None

        return subject, main_text, un

    def process_completed_powerful_idea(self, course, student, lesson_id):
        #work out which powerful idea the lesson is in, and set up the variables
        if lesson_id in ML_PROPORTION:
            pi = PI_PROPORTION
            mls = DICT_PROPORTION
        elif lesson_id in ML_UNCERTAINTY:
            pi = PI_UNCERTAINTY
            mls = DICT_UNCERTAINTY
        elif lesson_id in ML_REPRESENTATION:
            pi = PI_REPRESENTATION
            mls = DICT_REPRESENTATION
        elif lesson_id in ML_PATTERN:
            pi = PI_PATTERN
            mls = DICT_PATTERN
        elif lesson_id in ML_MEASUREMENT:
            pi = PI_MEASUREMENT
            mls = DICT_MEASUREMENT
        else:
            pi = None
            mls = None

        #check that the criteria matches and then set up the email subject and body if it does, otherwise return no values
        if pi is not None and mls is not None:
            progress_tracker = progress.UnitLessonCompletionTracker(course)
            completed, total = progress_tracker.get_number_lessons_completed_for_powerful_idea_or_unit(student, mls)
            if total - completed == 3:
                logging.info('pi completed')
                subject, main_text = self.get_email_text_pi_complete(pi)
            else:
                return None, None, None
        else:
            return None, None, None

        return subject, main_text, pi

    def get_email_text_pi_started(self, powerful_idea):
        subject = 'A message about your progress in Citizen Maths'
        text = "We are glad that you've made a start with {pi} in the Citizen Maths course. We encourage you to keep going; a good way to do this is likely to be to set aside a bit of time on most days to do one or two lessons until you've completed the whole course.".format(pi=powerful_idea)
        return subject, text

    def get_email_text_unit_complete(self, unit_name, unit_number):
        subject = 'A message about your progress in Citizen Maths'
        text = "We thought you'd like to know that you've only got one more lesson to go in {un} - {u}, in the Citizen Maths course. We encourage you to finish {un} now (if you have not already done so) whilst what you have been doing is fresh in your mind.".format(u=unit_name, un=unit_number)
        return subject, text

    def get_email_text_pi_complete(self, powerful_idea):
        subject = 'A message about your progress in Citizen Maths'
        text = "We thought you'd like to know that you've now got just three lessons to go to complete {pi} in the Citizen Maths course. We encourage you to finish {pi} now whilst things are fresh in your mind.".format(pi=powerful_idea)
        return subject, text

    def send_ae_email(self, email_address, subject, body):
        #sendgrid generic stuff
        sent = False
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

    #method to construct the main email body content of the adaptive encouragement email
    def get_ae_email_body(self, name, main_text, unit_id, lesson_id):
        hello = 'Hello {n},<br><br>'.format(n=name)

        regards = """<br><br>Regards,<br>
                     Seb Schmoller<br>
                     For the Citizen Maths Team<br>
                     <a href='https://citizenmaths.com/' target='_blank'>https://citizenmaths.com/</a><br><br>"""

        location = "<br>Notes<br>The course page this email was sent from was <a href='https://course.citizenmaths.com/main/unit?unit={u}&lesson={l}' target='_blank'>https://course.citizenmaths.com/main/unit?unit={u}&lesson={l}</a>. You may have got further on in Citizen Maths in the period before you opened this email.".format(u=unit_id, l=lesson_id)

        footer = """<br><br>You've received this email because when you registered for Citizen Maths you opted to be sent occasional encouraging emails about your progress with Citizen Maths.
                    <br><br>If you would like to unsubscribe to this service, please go to your profile page at <a href='https://course.citizenmaths.com/main/student/home' target='_blank'>https://course.citizenmaths.com/main/student/home</a> and click the \"Unsubscribe from encouragement emails\" button."""

        bodylist = [hello, main_text, regards, location, footer]

        body = ''.join(bodylist)

        return body

    def _set_gcb_html_element_class(self):
        """Select conditional CSS to hide parts of the unit page."""

        # TODO(jorr): Add an integration test for this once, LTI producer and
        # consumer code is completely checked in.

        gcb_html_element_class = []

        if self.request.get('hide-controls') == 'true':
            gcb_html_element_class.append('hide-controls')

        if self.request.get('hide-lesson-title') == 'true':
            gcb_html_element_class.append('hide-lesson-title')

        self.template_value['gcb_html_element_class'] = (
            ' '.join(gcb_html_element_class))

    def _apply_gcb_tags(self, text):
        return jinja_utils.get_gcb_tags_filter(self)(text)

    def _show_all_contents(self, student, unit, student_view):
        course = self.get_course()
        self.init_template_values(self.app_context.get_environ())

        display_content = []

        if unit.unit_header:
            display_content.append(self._apply_gcb_tags(unit.unit_header))

        if unit.pre_assessment:
            display_content.append(self.get_assessment_display_content(
                student, unit, course.find_unit_by_id(unit.pre_assessment),
                student_view, {}))

        for lesson in course.get_lessons(unit.unit_id):
            self.lesson_id = lesson.lesson_id
            self.lesson_is_scored = lesson.scored
            template_values = copy.copy(self.template_value)
            self.set_lesson_content(student, unit, lesson, student_view,
                                    template_values)
            display_content.append(self.render_template_to_html(
                template_values, 'lesson_common.html'))
            del self.lesson_id
            del self.lesson_is_scored

        if unit.post_assessment:
            display_content.append(self.get_assessment_display_content(
                student, unit, course.find_unit_by_id(unit.post_assessment),
                student_view, {}))

        if unit.unit_footer:
            display_content.append(self._apply_gcb_tags(unit.unit_footer))

        self.template_value['display_content'] = display_content

    def _showing_first_element(self, unit, lesson, assessment, is_activity):
        """Whether the unit page is showing the first element of a Unit."""

        # If the unit has a pre-assessment, then that's the first element;
        # we are showing the first element iff we are showing that assessment.
        if unit.pre_assessment:
            return (assessment and
                    str(assessment.unit_id) == str(unit.pre_assessment))

        # If there is no pre-assessment, there may be lessons.  If there
        # are any lessons, then the first element is the first unit component.
        # Iff we are showing that lesson, we're on the first component.
        unit_lessons = self.get_course().get_lessons(unit.unit_id)
        if unit_lessons:
            if lesson and lesson.lesson_id == unit_lessons[0].lesson_id:
                # If the first lesson has an activity, then we are showing
                # the first element if we are showing the lesson, and not
                # the activity.
                return not is_activity
            return False

        # If there is no pre-assessment and no lessons, then the post-assessment
        # is the first element.  We are on the first element if we're showing
        # that assessment.
        if unit.post_assessment:
            return (assessment and
                    str(assessment.unit_id) == str(unit.post_assessment))

        # If unit has no pre-assessment, no lessons, and no post-assessment,
        # then we're both at the first and last item.
        if (not unit.pre_assessment and
            not unit.post_assessment and
            not unit_lessons):

            return True

        return False

    def _showing_last_element(self, unit, lesson, assessment, is_activity):
        """Whether the unit page is showing the last element of a Unit."""

        # If the unit has a post-assessment, then that's the last element;
        # we are showing the last element iff we are showing that assessment.
        if unit.post_assessment:
            return (assessment and
                    str(assessment.unit_id) == str(unit.post_assessment))

        # If there is no post-assessment, there may be lessons.  If there
        # are any lessons, then the last element is the last unit component.
        # Iff we are showing that lesson, we're on the last component.
        unit_lessons = self.get_course().get_lessons(unit.unit_id)
        if unit_lessons:
            if lesson and lesson.lesson_id == unit_lessons[-1].lesson_id:
                # If the lesson has an activity, and we're showing the
                # activity, that's last.
                return is_activity == lesson.has_activity
            return False

        # If there is no post-assessment and there are no lessons, then
        # the pre-assessment is the last item in the unit.  We are on the
        # last element if we're showing that assessment.
        if unit.pre_assessment:
            return (assessment and
                    str(assessment.unit_id) == str(unit.pre_assessment))

        # If unit has no pre-assessment, no lessons, and no post-assessment,
        # then we're both at the first and last item.
        if (not unit.pre_assessment and
            not unit.post_assessment and
            not unit_lessons):

            return True

        return False

    def _show_single_element(self, student, unit, lesson, assessment,
                             student_view):
        # Add markup to page which depends on the kind of content.

        # need 'activity' to be True or False, and not the string 'true' or None
        is_activity = (self.request.get('activity') != '' or
                       '/activity' in self.request.path)
        display_content = []
        if (unit.unit_header and
            self._showing_first_element(unit, lesson, assessment, is_activity)):

            display_content.append(self._apply_gcb_tags(unit.unit_header))
        if assessment:
            if 'confirmation' in self.request.params:
                self.set_confirmation_content(student, unit, assessment,
                                              student_view)
                self.template_value['assessment_name'] = (
                    self.template_value.get('assessment_name').lower())
                display_content.append(self.render_template_to_html(
                    self.template_value, 'test_confirmation_content.html'))
            else:
                display_content.append(self.get_assessment_display_content(
                    student, unit, assessment, student_view,
                    self.template_value))
        elif lesson:
            self.lesson_id = lesson.lesson_id
            self.lesson_is_scored = lesson.scored
            if is_activity:
                self.set_activity_content(student, unit, lesson, student_view)
            else:
                self.set_lesson_content(student, unit, lesson,
                                        student_view, self.template_value)
            display_content.append(self.render_template_to_html(
                    self.template_value, 'lesson_common.html'))
        if (unit.unit_footer and
            self._showing_last_element(unit, lesson, assessment, is_activity)):

            display_content.append(self._apply_gcb_tags(unit.unit_footer))
        self.template_value['display_content'] = display_content

    def get_assessment_display_content(self, student, unit, assessment,
                                       student_view, template_values):
        template_values['page_type'] = ASSESSMENT_PAGE_TYPE
        template_values['assessment'] = assessment
        outline_element = student_view.find_element(
            [unit.unit_id, assessment.unit_id])
        if outline_element:
            template_values['back_button_url'] = outline_element.prev_link
            template_values['next_button_url'] = outline_element.next_link
        assessment_handler = assessments.AssessmentHandler()
        assessment_handler.app_context = self.app_context
        assessment_handler.request = self.request
        return assessment_handler.get_assessment_content(
            student, self.get_course(), assessment, as_lesson=True)

    def set_confirmation_content(self, student, unit, assessment,
                                 student_view):
        course = self.get_course()
        self.template_value['page_type'] = ASSESSMENT_CONFIRMATION_PAGE_TYPE
        self.template_value['unit'] = unit
        self.template_value['assessment'] = assessment
        self.template_value['is_confirmation'] = True
        self.template_value['assessment_name'] = assessment.title
        self.template_value['score'] = (
            course.get_score(student, str(assessment.unit_id)))
        self.template_value['is_last_assessment'] = (
            course.is_last_assessment(assessment))
        self.template_value['overall_score'] = (
            course.get_overall_score(student))
        self.template_value['result'] = course.get_overall_result(student)
        # Confirmation page's prev link goes back to assessment itself, not
        # assessment's previous page.
        outline_element = student_view.find_element(
            [unit.unit_id, assessment.unit_id])
        if outline_element:
            self.template_value['back_button_url'] = outline_element.link
            self.template_value['next_button_url'] = outline_element.next_link

    def set_activity_content(self, student, unit, lesson, student_view):
        self.template_value['page_type'] = ACTIVITY_PAGE_TYPE
        self.template_value['lesson'] = lesson
        self.template_value['lesson_id'] = lesson.lesson_id
        outline_element = student_view.find_element(
            [unit.unit_id, lesson.lesson_id])
        if outline_element:
            self.template_value['back_button_url'] = outline_element.prev_link
            self.template_value['next_button_url'] = outline_element.next_link
        self.template_value['activity'] = {
            'title': lesson.activity_title,
            'activity_script_src': (
                self.get_course().get_activity_filename(unit.unit_id,
                                                        lesson.lesson_id))}
        self.template_value['page_type'] = 'activity'
        self.template_value['title'] = lesson.activity_title

        if student_view.is_progress_recorded():
            # Mark this page as accessed. This is done after setting the
            # student progress template value, so that the mark only shows up
            # after the student visits the page for the first time.
            self.get_course().get_progress_tracker().put_activity_accessed(
                student, unit.unit_id, lesson.lesson_id)

    def _get_lesson_title(self, unit, lesson, student):
        title = None
        if self._LESSON_TITLE_PROVIDER:
            title = self._LESSON_TITLE_PROVIDER(
                self.app_context, lesson, student)
        if title is None:
            title = self._default_lesson_title_provider(
                self.app_context, unit, lesson, student)
        return title

    def set_lesson_content(self, student, unit, lesson, student_view,
                           template_values):
        template_values['page_type'] = UNIT_PAGE_TYPE
        template_values['lesson'] = lesson
        template_values['lesson_id'] = lesson.lesson_id
        outline_element = student_view.find_element(
            [unit.unit_id, lesson.lesson_id])
        if outline_element:
            template_values['back_button_url'] = outline_element.prev_link
            template_values['next_button_url'] = outline_element.next_link
        template_values['page_type'] = 'unit'
        template_values['title'] = self._get_lesson_title(unit, lesson, student)

        if not lesson.manual_progress and student_view.is_progress_recorded():
            # Mark this page as accessed. This is done after setting the
            # student progress template value, so that the mark only shows up
            # after the student visits the page for the first time.
            self.get_course().get_progress_tracker().put_html_accessed(
                student, unit.unit_id, lesson.lesson_id)


#apf: added new class for sending users ae emails who have been inactive
class InactiveUsersAdaptiveEncouragementCronHandler(utils.AbstractAllCoursesCronHandler):

    URL = '/cron/inactive_users/ae'

    @classmethod
    def is_globally_enabled(cls):
        return True

    @classmethod
    def is_enabled_for_course(cls, app_context):
        return True

    def cron_action(self, app_context, global_state):
        #we only want the cron code to run for our course namespace
        if app_context.get_namespace_name() == 'ns_main':
            logging.info(app_context.get_namespace_name())
            now = datetime.now()
            users = models.Student.all()
            course = courses.Course.get(app_context)
            logging.info(course)

            #concatenate the main lessons in a big dictionary
            dict_all_main_lessons = dict(DICT_PROPORTION_AL)
            dict_all_main_lessons.update(DICT_UNCERTAINTY_AL)
            dict_all_main_lessons.update(DICT_REPRESENTATION_AL)
            dict_all_main_lessons.update(DICT_PATTERN_AL)
            dict_all_main_lessons.update(DICT_MEASUREMENT_AL)

            #loop through the users
            for user in users:
                if user is not None:
                    #check the user is known by the gitkit email mapping datastore. this is because we are only interested in users after the ae code went live, which would only be gitkit users.
                    gu = gitkit.EmailMapping.get_by_user_id(user.user_id)
                    if gu is not None:
                        #set up some variables
                        af = user.additional_fields
                        sm = self.strip_value_from_additional_fields(af, 'SendMail')
                        email_address = self.strip_value_from_additional_fields(af, 'EmailAddress')
                        name = self.strip_value_from_additional_fields(af, 'GivenName')
                        #check that the student in question has given permission for adaptive encouragement emails to be sent
                        if sm == 'Yes':
                            user_id = user.user_id
                            #find out the current students progress throughout the course
                            progress_tracker = progress.UnitLessonCompletionTracker(course)
                            student_progress = progress_tracker.get_or_create_progress(user)
                            completed, total = progress_tracker.get_number_lessons_completed_for_powerful_idea_or_unit(user, dict_all_main_lessons)
                            sc = "number of lessons completed: {comp}".format(comp=completed)
                            logging.info(sc)

                            #get adaptive encouragement record for the student from the datastore. If one does not exist, create one.
                            ae = models.AdaptiveEncouragement.get_by_user_id(user_id)
                            if ae is None:
                                ae = models.AdaptiveEncouragement._add_new(user_id, 0, 0, 0, 0, None, None, None, False, False)

                            #if student registered more than a week ago and has yet to make a start in the course, send ths email
                            if user.enrolled_on < now-timedelta(days=7) and completed == 0 and ae.cron_inactive_not_started_email == False:
                                logging.info('enrolled more than 7 days ago and lessons completed is zero for user id:')
                                logging.info(user_id)
                                sent = self.send_ae_email(email_address, INACTIVE_EMAIL_SUBJECT, self.get_ae_email_body(name, INACTIVE_SEVEN_DAYS_EMAIL_TEXT))
                                if sent:
                                    logging.info('sent email to:')
                                    logging.info(email_address)
                                    #set this value to true so we do not send the email again on the next scheduled pass through of the code
                                    ae.cron_inactive_not_started_email = True

                            #if student registered more than two weeks ago, made a start in the course but has not completed it, send ths email
                            if user.last_seen_on < now-timedelta(weeks=2) and completed > 0 and progress_tracker.is_assessment_completed(student_progress, EOCQ_ASSESSMENT_ID) == False and ae.cron_inactive_started_email == False:
                                logging.info('last seen on more than 14 days ago and lessons completed more than zero but not done eocq for user id:')
                                logging.info(user_id)
                                if student_progress is not None and student_progress.updated_on is not None and student_progress.updated_on < now-timedelta(weeks=2):
                                    logging.info('progress updated more than two weeks ago')
                                    sent = self.send_ae_email(email_address, INACTIVE_EMAIL_SUBJECT, self.get_ae_email_body(name, INACTIVE_TWO_WEEKS_EMAIL_TEXT))
                                    if sent:
                                        logging.info('sent email to:')
                                        logging.info(email_address)
                                        #set this value to true so we do not send the email again on the next scheduled pass through of the code
                                        ae.cron_inactive_started_email = True

                            #save the adaptive encouragement record
                            ae.put()

    def strip_value_from_additional_fields(self, origin, token):
        value = None
        index = origin.find(token)
        if index >= 0:
            ss = origin[index:]
            end_index = ss.find('"]')
            if end_index > 0:
                value = ss[len(token) + 4:end_index]
        return value

    def send_ae_email(self, email_address, subject, body):
        sent = False
        if subject is not None and body is not None:
            #send the email!
            sg = sendgrid.SendGridClient(SENDGRID_API_KEY)
            message = sendgrid.Mail()
            message.set_subject(subject)
            message.set_html(body)
            message.set_from('<YOUR_FROM_EMAIL_ADDRESS_HERE>')
            message.add_to(email_address)
            status, msg = sg.send(message)
            if status == 200:
                sent = True

        return sent

    def get_ae_email_body(self, name, main_text):
        hello = 'Hello {n},<br><br>'.format(n=name)

        regards = """<br><br>Regards,<br>
                     Seb Schmoller<br>
                     For the Citizen Maths Team<br>
                     <a href='https://citizenmaths.com/' target='_blank'>https://citizenmaths.com/</a><br><br>"""

        footer = """<br>Notes<br>You've received this email because when you registered for Citizen Maths you opted to be sent occasional encouraging emails about your progress with Citizen Maths.
                    <br><br>If you would like to unsubscribe to this service, please go to your profile page at <a href='https://course.citizenmaths.com/main/student/home' target='_blank'>https://course.citizenmaths.com/main/student/home</a> and click the \"Unsubscribe from encouragement emails\" button."""

        bodylist = [hello, main_text, regards, footer]

        body = ''.join(bodylist)

        return body

class ReviewDashboardHandler(utils.BaseHandler):
    """Handler for generating the index of reviews that a student has to do."""

    def _populate_template(self, course, unit, review_steps):
        """Adds variables to the template for the review dashboard."""
        self.template_value['assessment_name'] = unit.title
        self.template_value['unit_id'] = unit.unit_id

        parent_unit = course.get_parent_unit(unit.unit_id)

        if parent_unit is not None:
            self.template_value['back_link'] = 'unit?unit=%s&assessment=%s' % (
                parent_unit.unit_id, unit.unit_id)
        else:
            self.template_value['back_link'] = (
                'assessment?name=%s' % unit.unit_id)

        self.template_value['event_xsrf_token'] = (
            crypto.XsrfTokenManager.create_xsrf_token('event-post'))
        self.template_value['review_dashboard_xsrf_token'] = (
            crypto.XsrfTokenManager.create_xsrf_token('review-dashboard-post'))

        self.template_value['REVIEW_STATE_COMPLETED'] = (
            domain.REVIEW_STATE_COMPLETED)

        self.template_value['review_steps'] = review_steps
        self.template_value['review_min_count'] = (
            unit.workflow.get_review_min_count())

        review_due_date = unit.workflow.get_review_due_date()
        if review_due_date:
            self.template_value['review_due_date'] = review_due_date.strftime(
                utils.HUMAN_READABLE_DATETIME_FORMAT)

        time_now = datetime.datetime.now()
        self.template_value['due_date_exceeded'] = (time_now > review_due_date)

    def get(self):
        """Handles GET requests."""
        student = self.personalize_page_and_get_enrolled()
        if not student:
            return

        course = self.get_course()
        rp = course.get_reviews_processor()
        unit, _ = extract_unit_and_lesson(self)
        if not unit:
            self.error(404)
            return

        self.template_value['navbar'] = {'course': True}

        if not course.needs_human_grader(unit):
            self.error(404)
            return

        # Check that the student has submitted the corresponding assignment.
        if not rp.does_submission_exist(unit.unit_id, student.get_key()):
            self.template_value['error_code'] = (
                'cannot_review_before_submitting_assignment')
            self.render('error.html')
            return

        review_steps = rp.get_review_steps_by(unit.unit_id, student.get_key())

        self._populate_template(course, unit, review_steps)
        required_review_count = unit.workflow.get_review_min_count()

        # The student can request a new submission if:
        # - all his/her current reviews are in Draft/Completed state, and
        # - he/she is not in the state where the required number of reviews
        #       has already been requested, but not all of these are completed.
        self.template_value['can_request_new_review'] = (
            len(review_steps) < required_review_count or
            models_review.ReviewUtils.has_completed_all_assigned_reviews(
                review_steps)
        )
        self.render('review_dashboard.html')

    def post(self):
        """Allows a reviewer to request a new review."""
        student = self.personalize_page_and_get_enrolled()
        if not student:
            return

        if not self.assert_xsrf_token_or_fail(
                self.request, 'review-dashboard-post'):
            return

        course = self.get_course()
        unit, unused_lesson = extract_unit_and_lesson(self)
        if not unit:
            self.error(404)
            return

        rp = course.get_reviews_processor()
        review_steps = rp.get_review_steps_by(unit.unit_id, student.get_key())
        self.template_value['navbar'] = {'course': True}

        if not course.needs_human_grader(unit):
            self.error(404)
            return

        # Check that the student has submitted the corresponding assignment.
        if not rp.does_submission_exist(unit.unit_id, student.get_key()):
            self.template_value['error_code'] = (
                'cannot_review_before_submitting_assignment')
            self.render('error.html')
            return

        # Check that the review due date has not passed.
        time_now = datetime.datetime.now()
        review_due_date = unit.workflow.get_review_due_date()
        if time_now > review_due_date:
            self.template_value['error_code'] = (
                'cannot_request_review_after_deadline')
            self.render('error.html')
            return

        # Check that the student can request a new review.
        review_min_count = unit.workflow.get_review_min_count()
        can_request_new_review = (
            len(review_steps) < review_min_count or
            models_review.ReviewUtils.has_completed_all_assigned_reviews(
                review_steps))
        if not can_request_new_review:
            self.template_value['review_min_count'] = review_min_count
            self.template_value['error_code'] = 'must_complete_more_reviews'
            self.render('error.html')
            return

        self.template_value['no_submissions_available'] = True

        try:
            review_step_key = rp.get_new_review(unit.unit_id, student.get_key())
            redirect_params = {
                'key': review_step_key,
                'unit': unit.unit_id,
            }
            self.redirect('/review?%s' % urllib.urlencode(redirect_params))
        except Exception:  # pylint: disable=broad-except
            review_steps = rp.get_review_steps_by(
                unit.unit_id, student.get_key())
            self._populate_template(course, unit, review_steps)
            self.render('review_dashboard.html')


class ReviewHandler(utils.BaseHandler):
    """Handler for generating the submission page for individual reviews."""

    # pylint: disable=too-many-statements
    def get(self):
        """Handles GET requests."""
        student = self.personalize_page_and_get_enrolled()
        if not student:
            return

        course = self.get_course()
        rp = course.get_reviews_processor()
        unit, unused_lesson = extract_unit_and_lesson(self)

        if not course.needs_human_grader(unit):
            self.error(404)
            return

        review_step_key = self.request.get('key')
        if not unit or not review_step_key:
            self.error(404)
            return

        try:
            review_step_key = db.Key(encoded=review_step_key)
            review_step = rp.get_review_steps_by_keys(
                unit.unit_id, [review_step_key])[0]
        except Exception:  # pylint: disable=broad-except
            self.error(404)
            return

        if not review_step:
            self.error(404)
            return

        # Check that the student is allowed to review this submission.
        if not student.has_same_key_as(review_step.reviewer_key):
            self.error(404)
            return

        model_version = course.get_assessment_model_version(unit)
        assert model_version in courses.SUPPORTED_ASSESSMENT_MODEL_VERSIONS
        self.template_value['model_version'] = model_version

        if model_version == courses.ASSESSMENT_MODEL_VERSION_1_4:
            configure_assessment_view = self.configure_assessment_view_1_4
            configure_readonly_review = self.configure_readonly_review_1_4
            configure_active_review = self.configure_active_review_1_4
        elif model_version == courses.ASSESSMENT_MODEL_VERSION_1_5:
            configure_assessment_view = self.configure_assessment_view_1_5
            configure_readonly_review = self.configure_readonly_review_1_5
            configure_active_review = self.configure_active_review_1_5
        else:
            raise ValueError('Bad assessment model version: %s' % model_version)

        self.template_value['navbar'] = {'course': True}
        self.template_value['unit_id'] = unit.unit_id
        self.template_value['key'] = review_step_key

        submission_key = review_step.submission_key
        submission_contents = student_work.Submission.get_contents_by_key(
            submission_key)

        configure_assessment_view(unit, submission_contents)

        review_due_date = unit.workflow.get_review_due_date()
        if review_due_date:
            self.template_value['review_due_date'] = review_due_date.strftime(
                utils.HUMAN_READABLE_DATETIME_FORMAT)

        review_key = review_step.review_key
        rev = rp.get_reviews_by_keys(
            unit.unit_id, [review_key])[0] if review_key else None

        time_now = datetime.datetime.now()
        show_readonly_review = (
            review_step.state == domain.REVIEW_STATE_COMPLETED or
            time_now > review_due_date)

        self.template_value['due_date_exceeded'] = (time_now > review_due_date)

        if show_readonly_review:
            configure_readonly_review(unit, rev)
        else:
            # Populate the review form,
            configure_active_review(unit, rev)

        self.template_value['assessment_xsrf_token'] = (
            crypto.XsrfTokenManager.create_xsrf_token('review-post'))
        self.template_value['event_xsrf_token'] = (
            crypto.XsrfTokenManager.create_xsrf_token('event-post'))

        # pylint: disable=protected-access
        self.render('review.html', additional_dirs=[assessments._TEMPLATES_DIR])

    def configure_assessment_view_1_4(self, unit, submission_contents):
        readonly_student_assessment = \
            assessments.create_readonly_assessment_params(
                self.get_course().get_assessment_content(unit),
                student_work.StudentWorkUtils.get_answer_list(
                    submission_contents))
        self.template_value[
            'readonly_student_assessment'] = readonly_student_assessment

    def configure_assessment_view_1_5(self, unit, submission_contents):
        self.template_value['html_review_content'] = unit.html_content
        self.template_value['html_reviewee_answers'] = transforms.dumps(
            submission_contents)

    def configure_readonly_review_1_4(self, unit, review_contents):
        readonly_review_form = assessments.create_readonly_assessment_params(
            self.get_course().get_review_content(unit),
            student_work.StudentWorkUtils.get_answer_list(review_contents))
        self.template_value['readonly_review_form'] = readonly_review_form

    def configure_readonly_review_1_5(self, unit, review_contents):
        self.template_value['readonly_review_form'] = True
        self.template_value['html_review_form'] = unit.html_review_form
        self.template_value['html_review_answers'] = transforms.dumps(
            review_contents)

    def configure_active_review_1_4(self, unit, review_contents):
        self.template_value['assessment_script_src'] = (
            self.get_course().get_review_filename(unit.unit_id))
        saved_answers = (
            student_work.StudentWorkUtils.get_answer_list(review_contents)
            if review_contents else [])
        self.template_value['saved_answers'] = transforms.dumps(saved_answers)

    def configure_active_review_1_5(self, unit, review_contents):
        self.template_value['html_review_form'] = unit.html_review_form
        self.template_value['html_review_answers'] = transforms.dumps(
            review_contents)

    def post(self):
        """Handles POST requests, when a reviewer submits a review."""
        student = self.personalize_page_and_get_enrolled()
        if not student:
            return

        if not self.assert_xsrf_token_or_fail(self.request, 'review-post'):
            return

        course = self.get_course()
        rp = course.get_reviews_processor()

        unit_id = self.request.get('unit_id')
        unit = self.find_unit_by_id(unit_id)
        if not unit or not course.needs_human_grader(unit):
            self.error(404)
            return

        review_step_key = self.request.get('key')
        if not review_step_key:
            self.error(404)
            return

        try:
            review_step_key = db.Key(encoded=review_step_key)
            review_step = rp.get_review_steps_by_keys(
                unit.unit_id, [review_step_key])[0]
        except Exception:  # pylint: disable=broad-except
            self.error(404)
            return

        # Check that the student is allowed to review this submission.
        if not student.has_same_key_as(review_step.reviewer_key):
            self.error(404)
            return

        self.template_value['navbar'] = {'course': True}
        self.template_value['unit_id'] = unit.unit_id

        # Check that the review due date has not passed.
        time_now = datetime.datetime.now()
        review_due_date = unit.workflow.get_review_due_date()
        if time_now > review_due_date:
            self.template_value['time_now'] = time_now.strftime(
                utils.HUMAN_READABLE_DATETIME_FORMAT)
            self.template_value['review_due_date'] = (
                review_due_date.strftime(utils.HUMAN_READABLE_DATETIME_FORMAT))
            self.template_value['error_code'] = 'review_deadline_exceeded'
            self.render('error.html')
            return

        mark_completed = (self.request.get('is_draft') == 'false')
        self.template_value['is_draft'] = (not mark_completed)

        review_payload = self.request.get('answers')
        review_payload = transforms.loads(
            review_payload) if review_payload else []
        try:
            rp.write_review(
                unit.unit_id, review_step_key, review_payload, mark_completed)
            course.update_final_grades(student)
        except domain.TransitionError:
            self.template_value['error_code'] = 'review_already_submitted'
            self.render('error.html')
            return

        self.render('review_confirmation.html')


class EventsRESTHandler(utils.BaseRESTHandler):
    """Provides REST API for an Event."""

    def get(self):
        """Returns a 404 error; this handler should not be GET-accessible."""
        self.error(404)
        return

    def _add_request_facts(self, payload_json):
        payload_dict = transforms.loads(payload_json)
        if 'loc' not in payload_dict:
            payload_dict['loc'] = {}
        loc = payload_dict['loc']
        loc['locale'] = self.get_locale_for(self.request, self.app_context)
        loc['language'] = self.request.headers.get('Accept-Language')
        loc['country'] = self.request.headers.get('X-AppEngine-Country')
        loc['region'] = self.request.headers.get('X-AppEngine-Region')
        loc['city'] = self.request.headers.get('X-AppEngine-City')
        lat_long = self.request.headers.get('X-AppEngine-CityLatLong')
        if lat_long:
            latitude, longitude = lat_long.split(',')
            loc['lat'] = float(latitude)
            loc['long'] = float(longitude)
        user_agent = self.request.headers.get('User-Agent')
        if user_agent:
            payload_dict['user_agent'] = user_agent
        payload_json = transforms.dumps(payload_dict).lstrip(
            models.transforms.JSON_XSSI_PREFIX)
        return payload_json

    def post(self):
        """Receives event and puts it into datastore."""

        COURSE_EVENTS_RECEIVED.inc()
        if not self.can_record_student_events():
            return

        request = transforms.loads(self.request.get('request'))
        if not self.assert_xsrf_token_or_fail(request, 'event-post', {}):
            return

        user = self.get_user()
        if not user:
            return

        source = request.get('source')
        payload_json = request.get('payload')
        payload_json = self._add_request_facts(payload_json)
        models.EventEntity.record(source, user, payload_json)
        COURSE_EVENTS_RECORDED.inc()

        self.process_event(user, source, payload_json)

    def process_event(self, user, source, payload_json):
        """Processes an event after it has been recorded in the event stream."""

        student = models.Student.get_enrolled_student_by_user(user)
        if not student:
            return

        payload = transforms.loads(payload_json)

        if 'location' not in payload:
            return

        source_url = payload['location']

        if source in TAGS_THAT_TRIGGER_BLOCK_COMPLETION:
            unit_id, lesson_id = get_unit_and_lesson_id_from_url(
                self, source_url)
            if unit_id is not None and lesson_id is not None:
                self.get_course().get_progress_tracker().put_block_completed(
                    student, unit_id, lesson_id, payload['index'])
        elif source in TAGS_THAT_TRIGGER_COMPONENT_COMPLETION:
            unit_id, lesson_id = get_unit_and_lesson_id_from_url(
                self, source_url)
            cpt_id = payload['instanceid']
            if (unit_id is not None and lesson_id is not None and
                cpt_id is not None):
                self.get_course().get_progress_tracker(
                    ).put_component_completed(
                        student, unit_id, lesson_id, cpt_id)
        elif source in TAGS_THAT_TRIGGER_HTML_COMPLETION:
            # Records progress for scored lessons.
            unit_id, lesson_id = get_unit_and_lesson_id_from_url(
                self, source_url)
            course = self.get_course()
            unit = course.find_unit_by_id(unit_id)
            lesson = course.find_lesson_by_id(unit, lesson_id)
            if (unit_id is not None and
                lesson_id is not None and
                not lesson.manual_progress):
                self.get_course().get_progress_tracker().put_html_completed(
                    student, unit_id, lesson_id)


def on_module_enabled(unused_custom_module):
    # Conform with convention for sub-packages within modules/courses; this
    # file doesn't have any module-registration-time work to do.
    pass


def get_namespaced_handlers():
    return [
        ('/activity', UnitHandler),
        ('/course', CourseHandler),
        ('/review', ReviewHandler),
        ('/reviewdashboard', ReviewDashboardHandler),
        ('/unit', UnitHandler)]
