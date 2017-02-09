# coursebuilder-adaptive-encouragement
Additional functionality based on when users complete certain actions, like completing a rating, or nearly finishing a unit, an email (if the user has consented) will be sent to encourage the user to continue with the course and to provide feedback if applicable.

##Important:

To use the emailing part of this code, you will need a sendgrid account and to have created sendgrid api token which is used to authenticate your account when using the API.
It is free to set up a sendgrid account at https://sendgrid.com/, and you get 12000 emails for free per month. Anymore than that, and you will have to refer to sendgrids price plan.

##Modifications to lib directory

-Added python-http-client.zip

-Added sendgrid-python-2.2.1.zip

-Added smtpapi-python-0.3.1.zip

The above libraries were added so that the course could use sendgrid for sending emails instead of the in built mail api.
This is because the in built mail api has a strict quota of 100 emails a day, and the course can send many more than that in a few hours during a busy period.
Also, sendgrid allows the course to send 12000 emails for free per month.

##Modifications to appengine_config.py

**Lines #111-114** - importing these extra libraries from the lib directory above into coursebuilder, so we can use them in the code.

```
#sendgrid
_Library('sendgrid-python-2.2.1.zip'),
_Library('smtpapi-python-0.3.1.zip'),
_Library('python-http-client.zip'),
```

##Modifications to cron.yaml

**Lines #22-24** - Added the URL and schedule to run the inactive users adaptive encouragement cron job

##Modifications to views/student_data_table.html

Modified content in this template for the data table in the student profile page. Taken some lines out, and added in new rows in the data table with custom functionality provided by extra code as mentioned in this README.

##Modifications to the code at controllers/utils.py

###Additional classes added:

**Line #1287** - `StudentAdaptiveEncouragementSubscriberHandler`

This handles the process of subscribing/unsubscribing to adaptive encouragement emails. This code is called when the relevant button on the Student profile page is clicked from within the data table.

**Line #1341** - `StudentMailingListSubscriberHandler`

This handles the process of subscribing/unsubscribing to being put on a mailing list. This code is called when the relevant button on the Student profile page is clicked from within the data table.

###Additional code to existing methods:

**Lines #1432-1448** in method `get` in class `StudentProfileHandler`

```
origin = student.additional_fields
sm = self.strip_name_from_additional_fields(origin, 'SendMail')
ae_subscribed = False
if sm == 'Yes':
    ae_subscribed = True

ml = self.strip_name_from_additional_fields(origin, 'MailList')
ml_subscribed = False
if ml == 'Yes':
    ml_subscribed = True

if student.name == None or not student.name or student.name.isspace():
    gn = self.strip_name_from_additional_fields(origin, 'GivenName')
    fn = self.strip_name_from_additional_fields(origin, 'FamilyName')
    name = gn + ' ' + fn
else:
    name = student.name
```

This segment set ups variables with the values found from the properties stored in additional_fields for the student in question from the Student entity.
It sets whether the student is signed up to adaptive encouragement emails or not, signed up to the mailing list or not, and sets their name.
These values are passed through to the student profile page to be shown to the student.

**Line #1456** in method `get` in class `StudentProfileHandler`

`self.template_value['student_name'] = name`

Sets the students name in the template for use when rendering.

**Lines #1472-1473** in method `get` in class `StudentProfileHandler`

```
self.template_value['ae_subscribed'] = ae_subscribed
self.template_value['ml_subscribed'] = ml_subscribed
```

Sets boolean values of whether the student is signed up to adaptive encouragement emails and a maling list, which is used in the template when rendering.

###Additional methods in class `StudentProfileHandler`

**Line #1490** - `strip_name_from_additional_fields` - used to find values set in additional_fields given the property key.

##Modifications to the code at models/models.py

###Additional classes added:

**Lines #1301-1343** - `class AdaptiveEncouragement(BaseEntity)`

The AdaptiveEncouragement class is the model that is used to store information about a student's adaptive encouragement progress in the datastore.
The fields that are stored include:

-the user id of the student the record belongs to.

-how many emails of each type (lesson and feedback type) have been sent in the week (limit of 4 emails of each allowed per week).

-a datetime of when the first email was sent in the week.

-a counter each for feedback and feedback with narrative which are submitted via the ratings module for coursebuilder.

-text fields that store the type of lesson email sent, whether it is starting a powerful idea or nearly completing a unit, so as not to send a duplicate email about this.

-whether the cron job emails (boolean value in the record) have been sent which deal with if a student has started the course, but then stopped all of a sudden, and if a student has registered for the course but has yet to make a start on the course.

It also contains a method to get the relevant record for updating by searching for it by user id.

##Modifications to the code at models/progress.py

###Additional methods added:

**Lines #1002-1015** - `get_number_lessons_completed_for_powerful_idea_or_unit(self, student, main_lessons)` added to class `UnitLessonCompletionTracker`

Finds the number of lessons completed by a student for a given range which is passed in as lesson id's. Returns the number of completed lessons by the student from the range as well as the total number of lessons passed in.

##Modifications to the code at modules/rating/rating.py

###Additional imports:

**Line #27**

`import sendgrid`

**Lines #46-47**

```
from datetime import datetime
from datetime import timedelta
```

The above imports allow the code to use sendgrid for sending emails, and to work out and compare date time values for certain criteria matching.

###Additional static variables:

**Line #62** - `SENDGRID_API_KEY = '<SENDGRID_API_KEY_HERE>'` - The sendgrid api token for your sendgrid account, so the api can authenticate and send the emails on your behalf. Replace the value with your own.

**Line #64** - `AE_LIVE_DATE = datetime(2016, 11, 1, 0, 0, 0, 0)` - The date on which adaptive encouragement went live. This is for a criteria match, so students who had registered before this date, would not receive one of the emails the code can send.

###Additional methods in class `RatingHandler`

**Line #180** - `process_feedback_adaptive_encouragement` - entry method for sending an adaptive encouragement email for a rating/feedback with no narrative feedback.

**Line #222** - `process_feedback_with_narrative_adaptive_encouragement` - entry method for sending an adaptive encouragement email for a rating/feedback with narrative feedback.

**Line #264** - `send_feedback_ae_email` - sendgrid code to send the adaptive encouragement email.

**Line #283** - `get_feedback_ae_email_body` - works out the main email body and subject, constructs it and returns the two (subject and body) as text.

**Line #330** - `strip_name_from_additional_fields` - gets the value of a property from the additional_fields from the student's record in the datastore.

###Additional code to existing methods:

**Lines #170-173** in method `post` in class `RatingHandler`

```
if additional_comments and len(additional_comments.strip()) >= 10:
    self.process_feedback_with_narrative_adaptive_encouragement(student, key)
elif additional_comments is None or len(additional_comments.strip()) == 0:
    self.process_feedback_adaptive_encouragement(student, key)
```

This segment provides an entry point into the adaptive encouragement code for ratings/feedback.

##Modifications to the code at modules/courses/courses.py

###Additional Code to existing methods

**Line #97** in method `register_module`

`[(lessons.InactiveUsersAdaptiveEncouragementCronHandler.URL, lessons.InactiveUsersAdaptiveEncouragementCronHandler)],`

The URL and class with the cron action in it is added to the routes in coursebuilder, so when the URL is called, it runs the cron code for checking for Inactive users to be send an adapative encouragement email
to start or return to the course.

##Modifications to the code at modules/courses/lessons.py

###Additional imports:

**Line #27**

`import sendgrid`

**Line #30**

`import ast`

**Line #50**

`from modules.gitkit import gitkit`

**Lines #54-55**

```
from datetime import datetime
from datetime import timedelta
```

The above imports allow the code to use sendgrid for sending emails, ast for converting a string from the datastore into a list, gitkit so the code can find users,
and to work out and compare date time values for certain criteria matching.

###Additional static variables:

**Line #74** - `SENDGRID_API_KEY = '<SENDGRID_API_KEY_HERE>'` - The sendgrid api token for your sendgrid account, so the api can authenticate and send the emails on your behalf. Replace the value with your own.

**Lines #76-80**

```
PI_PROPORTION = 'Proportion'
PI_REPRESENTATION = 'Representation'
PI_MEASUREMENT = 'Measurement'
PI_UNCERTAINTY = 'Uncertainty'
PI_PATTERN = 'Pattern'
```

The names of each powerful idea. For use in emails, and in the datastore.

**Lines #82-86**

```
ML_PROPORTION = [28, 29, 30, 31, 36, 37, 38, 39, 40, 3, 4, 5, 6, 23, 24, 25, 44, 45, 46, 47, 48, 52, 53, 54, 125, 56, 57, 58]
ML_UNCERTAINTY = [74, 75, 76, 80, 81, 82, 86, 87, 88, 126]
ML_REPRESENTATION = [98, 99, 100, 101, 105, 106, 107, 111, 112, 113]
ML_PATTERN = [129, 130, 131, 135, 136, 140, 141, 142]
ML_MEASUREMENT = [146, 147, 148, 149, 153, 154, 155, 159, 160, 161, 162, 166, 167, 168, 169]
```

The main lessons (these exclude the introduction lessons) in each powerful idea. This is used for working out progress.

**Lines #88-92**

```
DICT_PROPORTION = {22:[28, 29, 30, 31], 34:[36, 37, 38, 39, 40], 1:[3, 4, 5, 6, 23, 24, 25], 42:[44, 45, 46, 47, 48], 50:[52, 53, 54, 125, 56, 57, 58]}
DICT_UNCERTAINTY = {72:[74, 75, 76], 78:[80, 81, 82], 84:[86, 87, 88, 126]}
DICT_REPRESENTATION = {96:[98, 99, 100, 101], 103:[105, 106, 107], 109:[111, 112, 113]}
DICT_PATTERN = {127:[129, 130, 131], 133:[135, 136], 138:[140, 141, 142]}
DICT_MEASUREMENT = {144:[146, 147, 148, 149], 151:[153, 154, 155], 157:[159, 160, 161, 162], 164:[166, 167, 168, 169]}
```

The main lessons (these exclude the introduction lessons) in each powerful idea in a dictionary data type with the unit id as the key for each list of main lessons. This is used for working out progress.

**Lines #94-98**

```
DICT_PROPORTION_AL = {22:[27, 28, 29, 30, 31, 32], 34:[35, 36, 37, 38, 39, 40, 41], 1:[2, 3, 4, 5, 6, 23, 24, 25, 26], 42:[43, 44, 45, 46, 47, 48, 49], 50:[52, 53, 54, 125, 56, 57, 58, 59]}
DICT_UNCERTAINTY_AL = {72:[73, 74, 75, 76, 77], 78:[79, 80, 81, 82, 83], 84:[85, 86, 87, 88, 126, 90]}
DICT_REPRESENTATION_AL = {96:[97, 98, 99, 100, 101, 102], 103:[104, 105, 106, 107, 108], 109:[110, 111, 112, 113, 114]}
DICT_PATTERN_AL = {127:[128, 129, 130, 131, 132], 133:[134, 135, 136, 137], 138:[139, 140, 141, 142, 143]}
DICT_MEASUREMENT_AL = {144:[145, 146, 147, 148, 149, 150], 151:[152, 153, 154, 155, 156], 157:[158, 159, 160, 161, 162, 163], 164:[165, 166, 167, 168, 169, 170]}
```

All the lessons in each powerful idea in a dictionary data type with the unit id as the key for each list of lessons. This is used for working out progress.

**Lines #100-117**

```
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
```

The individual unit names.

**Lines #119-136**

```
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
```

The individual unit numbers.

**Lines #138-155**

```
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
```

The main lessons for each unit.

**Lines #157-174**

```
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
```

The main lessons for each unit in a dictionary format where the key is the unit id, and the value is a list of the main lessons for the unit.

**Line #176** - `EOCQ_ASSESSMENT_ID = 176` - The end of course questionnaire (which is an assessment in coursebuilder) id.

**Lines #178-180**

```
LOGIC_PI_STARTED = 0
LOGIC_UC = 1
LOGIC_PI_COMPLETED = 2
```

The type of list to get from the datastore to check if an adaptive encouragement email for lesson/course progress has been sent to the student for the current conditions or not.

**Lines #182-188**

```
INACTIVE_EMAIL_SUBJECT = "A message from the Citizen Maths team"
INACTIVE_SEVEN_DAYS_EMAIL_TEXT = """We noticed that in the week since you signed up for Citizen Maths, you seem not to have got started with the course.
                                    <br><br>We'd encourage you to make a start. If you do so, you can do as much or as little as you like in session.
                                    <br><br>In case of difficulty, feel free to get in touch and we will do what we can to help."""
INACTIVE_TWO_WEEKS_EMAIL_TEXT = """We noticed that it is two weeks since you last logged into Citizen Maths.
                                   <br><br>We hope very much that you will give Citizen Maths another try. 
                                   <br><br>In case of difficulty, feel free to get in touch and we will do what we can to help."""
```

The subject and body text for inactive users emails that the code can send.

###Additional classes added:

**Lines #1044-1166** - `InactiveUsersAdaptiveEncouragementCronHandler`

This class contains the cron action code that is run when the URL is called from the cron scheduler. It can send two variants of an email depending on the which the student matches, if any.
One being if the student has registered but not started the course at all, and the other being if the student has registered, made a start, but has been inactive for the last two weeks.

This class contains comments.

###Additional methods in class `UnitHandler`

**Line #456** - `strip_name_from_additional_fields` - gets a value from additional_fields and returns it given a property key.

**Line #466** - `process_lesson_adaptive_encouragement` - the entry method to the lesson/course progress adaptive encouragement side.

**Line #488** - `process_adaptive_encouragement_sending_logic` - method that processes each of the three types of adaptive encouragement emails that can be sent.

**Line #562** - `process_started_powerful_idea` - checks if the criteria given matches what is required for a started a powerful idea adaptive encouragement email.

**Line #597** - `process_completed_unit` - checks if the criteria given matches what is required for a nearly completed a unit adaptive encouragement email.

**Line #692** - `process_completed_powerful_idea` - checks if the criteria given matches what is required for a nearly completed a powerful idea adaptive encouragement email.

**Line #727** - `get_email_text_pi_started` - gets the email text for the started a powerful idea adaptive encouragement email.

**Line #732** - `get_email_text_unit_complete` - gets the email text for the nearly completed a unit adaptive encouragement email.

**Line #737** - `get_email_text_pi_complete` - gets the email text for the nearly completed a powerful idea adaptive encouragement email.

**Line #742** - `send_ae_email` - sends the adaptive encouragement email using sendgrid.

**Line #761** - `get_ae_email_body` - constructs the email body together with the parameters passed in.

###Additional code to existing methods:

**Line #372** in method `get` in class `UnitHandler`

`lesson_id = 0`

Initialiase a variable called lesson_id which will be used to pass through to the adaptive encouragement code.

**Line #377** in method `get` in class `UnitHandler`

`lesson_id = int(self.request.get('lesson'))`

Set the lesson_id variable with a value from the lesson parameter in the URL of the lesson page.

**Lines #446-447** in method `get` in class `UnitHandler`

```
if self.unit_id > 0 and self.unit_id == 50 and lesson_id == 0:
    lesson_id = 52
```

This is only here because we need to set the lesson id for a particular unit. As we know, when the lesson id is 0, it is the first lesson in the unit.
This lesson is a main lesson rather than an intro lesson, which we do not count usually for adaptive encouragement purposes.

**Lines #450-451** in method `get` in class `UnitHandler`

```
if self.unit_id > 0 and lesson_id > 0:
    self.process_lesson_adaptive_encouragement(student, course, self.unit_id, lesson_id)
```

This is the entry point to adaptive encouragement. As long as the code knows about a unit id and a lesson id, the process can start.
