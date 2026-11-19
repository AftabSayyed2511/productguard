"""
Seed verified reference products into ProductGuard database.
Reuses the genuine packaging images in legacy_store for the Electronics category.
"""
import os
import shutil
import uuid
from pathlib import Path
from app import create_app, db
from app.models.product import Product, ReferenceImage
from app.models.user import User
from app.models.audit import AdminActivity

BASE_DIR = Path(__file__).resolve().parent
LEGACY_STORE = BASE_DIR / "legacy_store"

ELECTRONICS_SEED = [
    {
        "name": "iPhone 15 Packaging",
        "brand": "Apple",
        "category": "Electronics",
        "sku": "AAPL-IP15-128G",
        "description": "Original retail packaging for Apple iPhone 15 with USB-C branding and color-matched device illustration.",
        "image": "i phone 15.jpeg",
        "angle": "front",
    },
    {
        "name": "Galaxy S25 Retail Box",
        "brand": "Samsung",
        "category": "Electronics",
        "sku": "SAM-S25-256G",
        "description": "Authentic packaging for Samsung Galaxy S25 featuring minimalist black recycled carton and reflective silver typography.",
        "image": "samsungs25.jpeg",
        "angle": "front",
    },
    {
        "name": "OnePlus 12 Packaging",
        "brand": "OnePlus",
        "category": "Electronics",
        "sku": "1P-12-512G",
        "description": "Signature red retail carton for OnePlus 12 with bold Hasselblad insignia and soft-touch matte finish.",
        "image": "oneplus12.jpeg",
        "angle": "front",
    },
    {
        "name": "20W USB-C Power Adapter",
        "brand": "Apple",
        "category": "Electronics",
        "sku": "AAPL-PWR-20W",
        "description": "Original Apple 20W power adapter compact box with green tear-tab and high-precision serial barcode print.",
        "image": "charger.jpeg",
        "angle": "front",
    },
    {
        "name": "Wireless Stereo Headphones",
        "brand": "Sony",
        "category": "Electronics",
        "sku": "SNY-WH-ANC",
        "description": "Retail carton for high-resolution noise-cancelling wireless headphones with 360 Reality Audio logo.",
        "image": "headphone.jpeg",
        "angle": "front",
    },
    {
        "name": "Fast-Charging Power Bank 20000mAh",
        "brand": "Anker",
        "category": "Electronics",
        "sku": "ANK-PB-20000",
        "description": "Retail box with embossed Anker logo, blue accents, holographic authenticity seal, and scratch-off verification panel.",
        "image": "powerbank.jpeg",
        "angle": "front",
    },
    {
        "name": "Inspiron Series Packaging",
        "brand": "Dell",
        "category": "Electronics",
        "sku": "DELL-INSP-15",
        "description": "Recycled cardboard transport packaging with official Dell roundel and tamper-evident security tape.",
        "image": "dell.jpeg",
        "angle": "front",
    },
    {
        "name": "Pavilion Laptop Box",
        "brand": "HP",
        "category": "Electronics",
        "sku": "HP-PAV-15",
        "description": "HP Pavilion outer shipping box featuring dark blue branding, energy star certification, and security sealing labels.",
        "image": "hp.jpeg",
        "angle": "front",
    },
    {
        "name": "IdeaPad Laptop Packaging",
        "brand": "Lenovo",
        "category": "Electronics",
        "sku": "LEN-IP-15",
        "description": "Official Lenovo retail carton with red Lenovo banner tag and high-contrast batch printing.",
        "image": "lenovo.jpeg",
        "angle": "front",
    },
    {
        "name": "Redmi Note Packaging",
        "brand": "Xiaomi",
        "category": "Electronics",
        "sku": "MI-RN-13PRO",
        "description": "Original Xiaomi Redmi retail carton with Mi logo watermark, clean white border, and serial barcode.",
        "image": "redmi.jpeg",
        "angle": "front",
    },
]


def seed_reference_products():
    """Populate database with genuine products and link verified reference imagery."""
    app = create_app("development")
    with app.app_context():
        db.create_all()

        ref_dir = Path(app.config["REFERENCE_UPLOAD_DIR"])
        ref_dir.mkdir(parents=True, exist_ok=True)

        admin = User.query.filter_by(role="admin").first()
        admin_id = admin.id if admin else None

        seeded_count = 0

        for item in ELECTRONICS_SEED:
            existing = Product.query.filter_by(product_name=item["name"], brand=item["brand"]).first()
            if existing:
                continue

            product = Product(
                product_name=item["name"],
                brand=item["brand"],
                category=item["category"],
                sku_or_upc=item["sku"],
                description=item["description"],
            )
            db.session.add(product)
            db.session.flush()

            # Copy image from legacy store if available
            source_img = LEGACY_STORE / item["image"]
            if source_img.exists():
                ext = source_img.suffix.lower().replace(".", "")
                if ext == "jpeg":
                    ext = "jpg"
                dest_filename = f"{uuid.uuid4().hex}.{ext}"
                dest_path = ref_dir / dest_filename
                shutil.copy2(source_img, dest_path)

                ref_image = ReferenceImage(
                    product_id=product.id,
                    image_path=f"references/{dest_filename}",
                    angle_or_view=item["angle"],
                    verification_status="verified",
                )
                db.session.add(ref_image)

            if admin_id:
                log = AdminActivity(
                    admin_id=admin_id,
                    action="SEED_PRODUCT",
                    details=f"System seeded reference product '{item['name']}' ({item['brand']}).",
                )
                db.session.add(log)

            seeded_count += 1

        db.session.commit()
        print(f"[+] Successfully seeded {seeded_count} verified reference products into database.")


if __name__ == "__main__":
    seed_reference_products()
