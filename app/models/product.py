import uuid
from datetime import datetime
from app import db


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_name = db.Column(db.String(160), nullable=False, index=True)
    brand = db.Column(db.String(100), nullable=False, index=True)
    category = db.Column(db.String(60), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    sku_or_upc = db.Column(db.String(64), unique=True, nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    reference_images = db.relationship(
        "ReferenceImage",
        backref="product",
        lazy="joined",
        cascade="all, delete-orphan",
        order_by="asc(ReferenceImage.created_at)",
    )
    scans = db.relationship(
        "Scan",
        backref="matched_product",
        lazy="dynamic",
        foreign_keys="Scan.matched_product_id",
    )

    def to_dict(self, include_images: bool = True) -> dict:
        """Convert product entity to dictionary representation."""
        data = {
            "id": self.id,
            "product_name": self.product_name,
            "brand": self.brand,
            "category": self.category,
            "description": self.description,
            "sku_or_upc": self.sku_or_upc,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "reference_image_count": len(self.reference_images),
        }
        if include_images:
            data["reference_images"] = [img.to_dict() for img in self.reference_images]
        return data

    def __repr__(self) -> str:
        return f"<Product {self.brand} - {self.product_name} ({self.category})>"


class ReferenceImage(db.Model):
    __tablename__ = "reference_images"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = db.Column(
        db.String(36),
        db.ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_path = db.Column(db.String(255), nullable=False)
    verification_status = db.Column(db.String(30), nullable=False, default="verified")
    embedding_path = db.Column(db.String(255), nullable=True)
    angle_or_view = db.Column(db.String(50), nullable=False, default="front")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert reference image entity to dictionary representation."""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "image_path": self.image_path,
            "verification_status": self.verification_status,
            "embedding_path": self.embedding_path,
            "angle_or_view": self.angle_or_view,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<ReferenceImage {self.id} for Product {self.product_id}>"
