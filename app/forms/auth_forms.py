from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    EqualTo,
    Regexp,
    ValidationError,
    Optional,
)
from app.models.user import User


class RegistrationForm(FlaskForm):
    full_name = StringField(
        "Full Name",
        validators=[
            DataRequired(message="Full name is required."),
            Length(min=2, max=120, message="Name must be between 2 and 120 characters."),
        ],
    )
    username = StringField(
        "Username",
        validators=[
            DataRequired(message="Username is required."),
            Length(min=3, max=64, message="Username must be between 3 and 64 characters."),
            Regexp(
                r"^[a-zA-Z0-9_.-]+$",
                message="Username may only contain alphanumeric characters, dots, underscores, and dashes.",
            ),
        ],
    )
    email = StringField(
        "Email Address",
        validators=[
            DataRequired(message="Email address is required."),
            Email(message="Please enter a valid email address."),
            Length(max=120),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=8, message="Password must contain at least 8 characters."),
        ],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="Passwords must match."),
        ],
    )
    submit = SubmitField("Create Account")

    def validate_email(self, field):
        """Ensure email is unique across all user accounts."""
        if User.query.filter_by(email=field.data.strip().lower()).first():
            raise ValidationError("This email address is already registered. Please sign in.")

    def validate_username(self, field):
        """Ensure username is unique across all user accounts."""
        if User.query.filter_by(username=field.data.strip()).first():
            raise ValidationError("This username is already taken. Please choose another.")


class LoginForm(FlaskForm):
    email = StringField(
        "Email Address",
        validators=[
            DataRequired(message="Email address is required."),
            Email(message="Please enter a valid email address."),
        ],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Password is required.")],
    )
    remember_me = BooleanField("Remember Me")
    submit = SubmitField("Sign In")


class ProfileForm(FlaskForm):
    full_name = StringField(
        "Full Name",
        validators=[
            DataRequired(message="Full name is required."),
            Length(min=2, max=120),
        ],
    )
    email = StringField(
        "Email Address",
        validators=[
            DataRequired(message="Email address is required."),
            Email(message="Please enter a valid email address."),
        ],
    )
    current_password = PasswordField("Current Password", validators=[Optional()])
    new_password = PasswordField(
        "New Password (leave blank to keep current)",
        validators=[
            Optional(),
            Length(min=8, message="New password must be at least 8 characters."),
        ],
    )
    confirm_new_password = PasswordField(
        "Confirm New Password",
        validators=[
            EqualTo("new_password", message="New passwords must match."),
        ],
    )
    submit = SubmitField("Update Profile")
