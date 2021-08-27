from django.forms import CharField, DateTimeField
from django.forms.widgets import DateInput, Select
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.forms import ModelForm, Form

from crispy_forms.layout import Layout, Div, Field, HTML, Button
from crispy_forms.bootstrap import PrependedText
from crispy_forms.helper import FormHelper

from home.models import User, Grade, Course
from planetterp.settings import DATE_FORMAT
from home.utils import semester_name

class ProfileForm(ModelForm):
    username = CharField(
        required=False,
        disabled=True,
        label_suffix=None
    )

    date_joined = DateTimeField(
        required=False,
        disabled=True,
        label_suffix=None,
        widget=DateInput(format=DATE_FORMAT)
    )

    class Meta:
        # This is a temporary workaround for
        # https://discord.com/channels/784561204289994753/879121341159186453/879124088226992209
        # and needs to be resolved properly in the future
        model = User()
        fields = ["username", "email", "date_joined", "send_review_email"]
        help_text = {
            "username": User._meta.get_field("username").help_text
        }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.user = kwargs.get("instance")
        email = self.fields['email']

        if self.user.email:
            email.disabled = True
            self.fields['send_review_email'].label = (
                "Email me updates pertaining to the status of my reviews"
            )
        else:
            self.fields.pop("send_review_email")
            email.error_messages['unique'] = User.error_message_unique("email", include_anchor=False)

        self.field_errors = self.create_field_errors()
        self.helper = FormHelper()
        self.helper.form_id = 'profile-form'
        self.helper.field_class = 'px-0'
        self.helper.form_show_errors = False
        self.helper.layout = self.generate_layout()

    def create_field_errors(self):
        field_errors = {}

        for field in self.fields:
            if_condition = f'{{% if form.{field}.errors %}} '
            error_html = (
                f'<div id="{{{{ form.{field}.name }}}}_errors"'
                ' class="invalid-feedback" style="font-size: 15px">'
                f' {{{{ form.{field}.errors|striptags }}}}</div>'
            )
            endif = ' {% endif %}'
            field_errors[field] = HTML(if_condition + error_html + endif)

        return field_errors

    def generate_layout(self):
        if self.user.email:
            email_placeholder = None
            send_review_email_errors = self.field_errors['send_review_email']
            send_review_email = Field(
                'send_review_email',
                wrapper_class="profile-form-field"
            )

        else:
            email_placeholder = "Enter an email address"
            send_review_email = None
            send_review_email_errors = None

        layout = Layout(
            'username',
            'date_joined',
            PrependedText(
                'email',
                mark_safe('<i id="email-field-info" class="fas fa-info-circle"></i>'),
                placeholder=email_placeholder,
                wrapper_class="mb-0"
            ),
            self.field_errors['email'],
            send_review_email,
            send_review_email_errors,
            Div(
                Button(
                    'save',
                    'Save',
                    css_class="btn-primary",
                    onClick="updateProfile()"
                ),
                Div(
                    css_id="profile-form-success",
                    css_class="col text-success text-center d-none",
                    style="font-size: 20px"
                ),
                css_class="mt-3"
            )
        )

        return layout

# The "Lookup by course" feature on /grades
class HistoricCourseGradeLookupForm(Form):
    course = CharField(required=True)
    semester = CharField(required=False, widget=Select())
    # TODO: change section into select menue with all sections offered during
    #   the specified scourse/semester
    section = CharField(required=False)

    def __init__(self, course_name=None, **kwargs):
        super().__init__(**kwargs)
        if course_name:
            # If user specified the course, only display semesters when
            # that course was offered
            course_obj = Course.objects.filter(name=course_name).first()
            grades = Grade.objects.filter(course=course_obj).values('semester').distinct()
        else:
            # Otherwise, only display semesters we have data for
            grades = Grade.objects.values('semester').distinct()

        semester_choices = [(grade['semester'], semester_name(grade['semester'])) for grade in grades]
        self.fields['semester'].widget.choices = [("", "Select a semester...")] + semester_choices

        self.field_errors = self.create_field_errors()

        self.helper = FormHelper()
        self.helper.field_class = 'col-sm-3'
        self.helper.label_class = 'col-form-label'
        self.helper.form_id = "course-lookup-form"
        self.helper.form_show_errors = False
        self.helper.layout = self.generate_layout()

    def create_field_errors(self):
        field_errors = {}

        for field in self.fields:
            if_condition = f'{{% if form.{field}.errors %}} '
            error_html = (
                f'<div id="{{{{ form.{field}.name }}}}_errors"'
                ' class="invalid-feedback lookup-error" style="font-size: 15px">'
                f' {{{{ form.{field}.errors|striptags }}}}</div>'
            )
            endif = ' {% endif %}'
            field_errors[field] = HTML(if_condition + error_html + endif)

        return field_errors

    def generate_layout(self):
        return Layout(
            Field(
                'course',
                placeholder="Enter a course...",
                id="course-search",
                css_class="autocomplete",
                wrapper_class="row justify-content-center"
            ),
            Div(
                Field(
                    'semester',
                    id="semester-search",
                    wrapper_class="row justify-content-center",
                    onChange="semesterSearch()"
                ),
                css_id="semester-search-input",
                style="display: none;"
            ),
            Div(
                Field(
                    'section',
                    placeholder="Enter a section...",
                    id="section-search",
                    css_class="autocomplete",
                    wrapper_class="row justify-content-center",
                    onkeypress="sectionSearch(event)"
                ),
                css_id="section-search-input",
                style="display: none;"
            )
        )

    def clean(self):
        super().clean()
        clean_course = self.cleaned_data['course']
        clean_section = self.cleaned_data.get('section', None)

        course = Course.objects.filter(name=clean_course).first()
        course_data = Grade.objects.filter(course=course).first()
        section = Grade.objects.filter(section=clean_section).first()
        if not course:
            message = "We don't have record of that course"
            self.add_error('course', ValidationError(message, code="INVALID_COURSE"))
        if not course_data:
            message = "No grade data available for that course"
            self.add_error('course', ValidationError(message, code="NO_DATA"))
        if clean_section and not section:
            message = "We don't have record of that section for this course"
            self.add_error('section', ValidationError(message, code="INVALID_SECTION"))

        return self.cleaned_data
