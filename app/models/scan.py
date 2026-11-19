import uuid
from datetime import datetime
from app import db


class Scan(db.Model):
    __tablename__ = "scans"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    matched_product_id = db.Column(
        db.String(36),
        db.ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    matched_reference_image_id = db.Column(
        db.String(36),
        db.ForeignKey("reference_images.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_image_path = db.Column(db.String(255), nullable=False)
    similarity_score = db.Column(db.Float, nullable=False, default=0.0)
    assessment_status = db.Column(db.String(40), nullable=False, index=True)
    processing_time_ms = db.Column(db.Integer, nullable=False, default=0)
    notes = db.Column(db.Text, nullable=True)
    scanned_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    # Reference relationship for the exact matched image
    matched_reference = db.relationship(
        "ReferenceImage",
        foreign_keys=[matched_reference_image_id],
        lazy="joined",
    )

    def to_dict(self) -> dict:
        """Convert scan record to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "matched_product": (
                self.matched_product.to_dict(include_images=False)
                if self.matched_product
                else None
            ),
            "matched_reference_image_path": (
                self.matched_reference.image_path if self.matched_reference else None
            ),
            "uploaded_image_path": self.uploaded_image_path,
            "similarity_score": round(self.similarity_score, 4),
            "similarity_percentage": round(self.similarity_score * 100, 2),
            "assessment_status": self.assessment_status,
            "processing_time_ms": self.processing_time_ms,
            "scanned_at": self.scanned_at.isoformat() if self.scanned_at else None,
            "notes": self.notes,
        }

    def __repr__(self) -> str:
        return f"<Scan {self.id} Status={self.assessment_status} Score={self.similarity_score}>"
