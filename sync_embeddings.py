"""
Precompute and cache MobileNetV2 feature embeddings for all verified reference products.
Stores serialized vectors in app/static/uploads/embeddings/*.npy.
"""
from app import create_app, db
from app.models.product import ReferenceImage
from app.ai.matcher import sync_all_reference_embeddings


def main():
    app = create_app("development")
    with app.app_context():
        total_refs = ReferenceImage.query.filter_by(is_active=True).count()
        print(f"[*] Found {total_refs} active reference image records.")
        print("[*] Synchronizing feature embeddings with MobileNetV2...")

        newly_computed = sync_all_reference_embeddings(app)
        print(f"[+] Successfully computed and cached {newly_computed} new embedding vectors.")


if __name__ == "__main__":
    main()
