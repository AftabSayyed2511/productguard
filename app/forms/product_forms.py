from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    MultipleFileField,
    SubmitField,
)
from wtforms.fields.choices import SelectChoice
from wtforms.validators import DataRequired, Length, Optional

CATEGORY_CHOICES = [
    SelectChoice("Electronics", "Electronics"),
    SelectChoice("Cosmetics", "Cosmetics"),
    SelectChoice("Clothing", "Clothing"),
    SelectChoice("Personal Care", "Personal Care"),
    SelectChoice("Packaged Goods", "Packaged Goods"),
]

VIEW_CHOICES = [
    SelectChoice("front", "Front Packaging"),
    SelectChoice("back", "Back / Label"),
    SelectChoice("side", "Side Profile"),
    SelectChoice("seal", "Seal / Tamper Band"),
    SelectChoice("box", "Outer Box / Carton"),
]


class ProductForm(FlaskForm):
    product_name = StringField(
        "Product Name",
        validators=[
            DataRequired(message="Product name is required."),
            Length(min=2, max=160, message="Name must be between 2 and 160 characters."),
        ],
    )
    brand = StringField(
        "Brand / Manufacturer",
        validators=[
            DataRequired(message="Brand name is required."),
            Length(min=2, max=100, message="Brand must be between 2 and 100 characters."),
        ],
    )
    category = SelectField(
        "Category",
        choices=CATEGORY_CHOICES,
        validators=[DataRequired(message="Please select a category.")],
    )
    description = TextAreaField(
        "Description & Packaging Notes",
        validators=[Optional(), Length(max=2000)],
    )
    sku_or_upc = StringField(
        "Product Identifier (SKU / UPC / Barcode)",
        validators=[Optional(), Length(max=64)],
    )
    images = MultipleFileField(
        "Verified Reference Packaging Images",
        validators=[Optional()],
    )
    angle_or_view = SelectField(
        "Primary Viewpoint / Angle",
        choices=VIEW_CHOICES,
        default="front",
    )
    submit = SubmitField("Save Product")


class ReferenceImageUploadForm(FlaskForm):
    image = FileField(
        "Reference Packaging Image",
        validators=[
            DataRequired(message="Please select an image to upload."),
            FileAllowed(["jpg", "jpeg", "png"], "Only JPEG, JPG, and PNG images are allowed."),
        ],
    )
    angle_or_view = SelectField(
        "Packaging Viewpoint / Angle",
        choices=VIEW_CHOICES,
        default="front",
    )
    submit = SubmitField("Upload Reference Image")
