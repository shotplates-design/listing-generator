"""Streamlit review form. Drafts stay on this machine and nothing is posted."""

from __future__ import annotations

import html
import json

import streamlit as st

from listing_generator.export import ExportError, ListingExport
from listing_generator.generator import ListingGenerator
from listing_generator.models import ClothingItem, FacebookFulfillment, Fields, PhotoRef, PhotoRoles, Platforms
from listing_generator.money import Money, MoneyError
from listing_generator.text import Conditions, Departments
from listing_generator.vision.errors import VisionError
from listing_generator.vision.factory import VisionProviders
from listing_generator.vision.images import ImagePrep
from listing_generator.vision.parser import ExtractionParser
from listing_generator.vision.sample import SamplePhotos


class ListingApp:
    """Photo upload, an editable reading, then one tab per marketplace."""

    @staticmethod
    def render() -> None:
        st.set_page_config(page_title="Listing Generator", page_icon="✂", layout="wide")
        ListingApp._style()
        ListingApp._apply_pending()
        ListingApp._header()
        ListingApp._sidebar()
        photos = ListingApp._photos()
        if st.session_state.get("step") in {"details", "listings"}:
            ListingApp._details()
        if st.session_state.get("step") == "listings":
            ListingApp._listings()

    @staticmethod
    def _style() -> None:
        st.markdown(
            """
            <style>
              @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,560;9..144,650&family=Outfit:wght@400;500;600&display=swap');
              html, body, [class*="css"] { font-family: Outfit, "Segoe UI", sans-serif; }
              h1, h2, h3 { font-family: Fraunces, Georgia, serif; letter-spacing: -0.03em; }
              .block-container { padding-top: 1.5rem; max-width: 1180px; }
              .banner {
                background: #1c1915; color: #f6f1e8; border-radius: 16px;
                padding: 1.3rem 1.5rem 1.1rem; margin-bottom: 1rem;
              }
              .banner h1 { color: #f6f1e8; margin: 0 0 0.3rem; font-size: 2.4rem; }
              .banner p { margin: 0; color: #e4d8c4; font-size: 1.05rem; }
              .flag { color: #8a4b08; font-size: 0.92rem; margin: -0.4rem 0 0.6rem; }
              .quiet { color: #5c564c; font-size: 0.92rem; }
              div[data-testid="stMetric"] {
                background: #fffdf8; border: 1px solid #e4d8c4; border-radius: 12px; padding: 0.6rem 0.8rem;
              }
            </style>
            """,
            unsafe_allow_html=True,
        )

    @staticmethod
    def _header() -> None:
        st.markdown(
            """
            <div class="banner">
              <h1>Listing Generator</h1>
              <p>Upload photos of one clothing item. Correct the reading, then copy a draft for eBay, Poshmark, Depop, Mercari, Whatnot, or Facebook Marketplace. Nothing is posted.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    @staticmethod
    def _sidebar() -> None:
        info = VisionProviders.describe()
        with st.sidebar:
            st.subheader("Vision")
            st.write(f"Provider: {info['provider']}")
            st.write(f"Model: {info['model']}")
            if info["provider"] == "gemini":
                st.write("API key: set" if info["key_configured"] else "API key: missing")
            st.caption(str(info["note"]))
            polish = "on" if info["polish"] else "off"
            st.write(f"Language polish: {polish}")
            st.caption("Set LISTING_LLM_POLISH=1 to rewrite drafts. Titles are cut back to the platform limit.")
            st.caption("Fee rates live in config/fees.yaml. The download matches schema/listing.v1.schema.json.")

    @staticmethod
    def _photos() -> None:
        st.subheader("Photos")
        st.caption("Add the front, back, brand tag, care tag, and any flaws. Up to 8 photos. Measurements are never guessed.")
        uploads = st.file_uploader(
            "Photos of the item",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
        info = VisionProviders.describe()
        if info["provider"] == "mock":
            st.caption(
                "Offline mode. The hoodie button replays a recorded reading of the included photos. "
                "The sample button does not look at pixels."
            )
            if st.button("Analyze included hoodie photos", type="primary"):
                ListingApp._analyze_hoodie_fixture()
            if st.button("Analyze built-in sample photos"):
                ListingApp._analyze_sample()
        if not uploads:
            return
        names = [upload.name for upload in uploads]
        if st.session_state.get("upload_names") != names:
            st.session_state.upload_names = names
            for key in list(st.session_state.keys()):
                if key.startswith("role_") or key.startswith("order_"):
                    del st.session_state[key]
        columns = st.columns(min(4, len(uploads)))
        for index, upload in enumerate(uploads):
            with columns[index % len(columns)]:
                st.image(upload.getvalue(), caption=upload.name, width="stretch")
                if f"role_{index}" not in st.session_state:
                    st.session_state[f"role_{index}"] = PhotoRoles.default_for_index(index)
                if f"order_{index}" not in st.session_state:
                    st.session_state[f"order_{index}"] = index
                st.selectbox("Role", PhotoRoles.CHOICES, key=f"role_{index}")
                st.number_input("Order", min_value=0, step=1, key=f"order_{index}")
        if st.button("Read photos", type="primary"):
            ListingApp._analyze_uploads(uploads)

    @staticmethod
    def _analyze_uploads(uploads) -> None:
        try:
            files = [(upload.name, upload.getvalue()) for upload in uploads]
            prepared = ImagePrep.prepare_many(files)
            provider = VisionProviders.from_env()
            result = ExtractionParser.parse(provider.analyze(prepared), provider=provider.name, model=provider.model)
            photos = [
                {
                    "path_or_url": upload.name,
                    "role": st.session_state.get(f"role_{index}", PhotoRoles.default_for_index(index)),
                    "order": int(st.session_state.get(f"order_{index}", index)),
                }
                for index, upload in enumerate(uploads)
            ]
        except VisionError as exc:
            st.error(str(exc))
            return
        ListingApp._store_result(result, photos, "Reading ready. Blank fields were not filled in.", images=files)

    @staticmethod
    def _analyze_sample() -> None:
        try:
            files = SamplePhotos.build()
            prepared = ImagePrep.prepare_many(files)
            provider = VisionProviders.from_env()
            result = ExtractionParser.parse(provider.analyze(prepared), provider=provider.name, model=provider.model)
        except VisionError as exc:
            st.error(str(exc))
            return
        photos = [
            {"path_or_url": name, "role": PhotoRoles.default_for_index(index), "order": index}
            for index, (name, _data) in enumerate(files)
        ]
        st.session_state.sample_images = files
        ListingApp._store_result(
            result,
            photos,
            "Sample reading loaded. These cards are not a live model, and measurements were left blank.",
            images=files,
        )

    @staticmethod
    def _analyze_hoodie_fixture() -> None:
        from listing_generator.fixtures import HoodieFixture

        files = HoodieFixture.images()
        result = ExtractionParser.parse(
            HoodieFixture.vision_response(),
            provider="recorded",
            model="assc-hoodie-v1",
        )
        photos = [
            {"path_or_url": name, "role": role, "order": index}
            for index, (name, _data, role) in enumerate(HoodieFixture.manifest())
        ]
        ListingApp._store_result(
            result,
            photos,
            "Recorded reading for the included Anti Social Social Club photos. "
            "The ruler photo supplied pit to pit 23 in and length 27 in. Nothing was posted.",
            images=[(name, data) for name, data, _role in HoodieFixture.manifest()],
        )

    @staticmethod
    def _store_result(result, photos, notice: str, images=None) -> None:
        item = result.item
        st.session_state.pending = {
            "brand": item.brand,
            "item_type": item.item_type,
            "size_tagged": item.size_tagged,
            "color": item.color,
            "material": item.material,
            "origin": item.origin,
            "condition": item.condition,
            "flaws": item.flaws,
            "style_era": item.style_era,
            "gender_department": item.gender_department,
            "field_flags": dict(item.field_flags),
            "field_confidence": dict(item.field_confidence),
            "review_notes": list(item.review_notes),
            "discarded": result.discarded,
            "photos": photos,
            "notice": notice,
            "step": "details",
            "extracted_measurements": dict(item.measurements),
            "fixture_images": images or [],
            **{f"meas_{key}": item.measurements.get(key, "") for key, _label in Fields.MEASUREMENTS},
        }
        st.rerun()

    @staticmethod
    def _apply_pending() -> None:
        pending = st.session_state.get("pending")
        if not pending:
            return
        for key, value in pending.items():
            st.session_state[key] = value
        st.session_state.pending = None

    @staticmethod
    def _details() -> None:
        st.subheader("Check the reading")
        photos = st.session_state.get("fixture_images") or []
        if photos:
            columns = st.columns(min(6, len(photos)))
            for index, (name, data) in enumerate(photos):
                columns[index % len(columns)].image(data, caption=name, width="stretch")
        if st.session_state.get("notice"):
            st.info(st.session_state.notice)
        notes = st.session_state.get("review_notes") or []
        for note in notes:
            st.warning(note)
        flags = st.session_state.get("field_flags") or {}
        confidence = st.session_state.get("field_confidence") or {}
        left, right = st.columns(2)
        with left:
            ListingApp._text("brand", "Brand", flags, confidence)
            ListingApp._text("item_type", "Item type", flags, confidence)
            ListingApp._select("gender_department", "Department", Departments.CHOICES, flags, confidence)
            ListingApp._text("size_tagged", "Size on tag", flags, confidence)
            ListingApp._text("color", "Color", flags, confidence)
        with right:
            ListingApp._text("material", "Material", flags, confidence)
            ListingApp._text("origin", "Origin", flags, confidence)
            ListingApp._select("condition", "Condition", Conditions.CHOICES, flags, confidence)
            ListingApp._text("style_era", "Style or era", flags, confidence)
            ListingApp._area("flaws", "Flaws, one per line", flags, confidence)
        st.markdown("**Measurements**")
        ListingApp._flag("measurements", flags, confidence)
        measure_cols = st.columns(4)
        for index, (key, label) in enumerate(Fields.MEASUREMENTS):
            with measure_cols[index % 4]:
                st.text_input(label, key=f"meas_{key}", placeholder="leave blank")
        st.markdown("**Price**")
        st.caption("Optional. A price is not read from the photos. Leave these blank to skip the fee math.")
        price_cols = st.columns(4)
        with price_cols[0]:
            st.text_input("Cost basis", key="cost_basis", placeholder="18.00")
        with price_cols[1]:
            st.text_input("Target asking price", key="target_price", placeholder="40.00")
        with price_cols[2]:
            st.text_input("Buyer-paid shipping", key="buyer_paid_shipping", placeholder="0.00")
        with price_cols[3]:
            st.text_input("Sales tax collected", key="sales_tax", placeholder="0.00")
        ListingApp._select(
            "facebook_fulfillment",
            "Facebook fulfillment",
            FacebookFulfillment.CHOICES,
            {},
            {},
        )
        st.caption("Local pickup has no Facebook fee. Shipped checkout uses the selling fee in config/fees.yaml, which is flagged to verify.")
        discarded = st.session_state.get("discarded") or []
        if discarded:
            with st.expander("Readings left blank"):
                for row in discarded:
                    st.write(f"**{row.field}** — {row.reason}")
                    if row.value:
                        st.caption(row.value)
        if st.button("Draft listings", type="primary"):
            ListingApp._draft()

    @staticmethod
    def _text(key: str, label: str, flags: dict, confidence: dict) -> None:
        st.text_input(label, key=key)
        ListingApp._flag(key, flags, confidence)

    @staticmethod
    def _area(key: str, label: str, flags: dict, confidence: dict) -> None:
        st.text_area(label, key=key, height=96)
        ListingApp._flag(key, flags, confidence)

    @staticmethod
    def _select(key: str, label: str, choices: tuple, flags: dict, confidence: dict) -> None:
        labels = [choice[1] for choice in choices]
        current = st.session_state.get(key, "")
        index = next((i for i, (value, _label) in enumerate(choices) if value == current), 0)
        selected = st.selectbox(label, labels, index=index, key=f"{key}_label")
        st.session_state[key] = next(value for value, text in choices if text == selected)
        ListingApp._flag(key, flags, confidence)

    @staticmethod
    def _flag(key: str, flags: dict, confidence: dict) -> None:
        message = flags.get(key)
        level = confidence.get(key)
        if not message and not level:
            return
        bits = []
        if level:
            bits.append(f"confidence {level}")
        if message:
            bits.append(message)
        safe = " · ".join(html.escape(bit, quote=True) for bit in bits)
        st.markdown(f'<div class="flag">{safe}</div>', unsafe_allow_html=True)

    @staticmethod
    def _draft() -> None:
        try:
            item = ListingApp._item_from_form()
        except MoneyError as exc:
            st.error(str(exc))
            return
        try:
            listings = ListingGenerator.generate(item)
            photos = [
                PhotoRef(path_or_url=row["path_or_url"], role=row["role"], order=int(row["order"]))
                for row in st.session_state.get("photos") or []
            ]
            document = ListingExport.build(
                item,
                listings,
                photos,
                discarded=st.session_state.get("discarded") or [],
            )
        except (ExportError, ValueError) as exc:
            st.error(str(exc))
            return
        st.session_state.listings_doc = document
        st.session_state.step = "listings"
        st.rerun()

    @staticmethod
    def _item_from_form() -> ClothingItem:
        original_confidence = dict(st.session_state.get("field_confidence") or {})
        original_flags = dict(st.session_state.get("field_flags") or {})
        measurements = {
            key: st.session_state.get(f"meas_{key}", "").strip()
            for key, _label in Fields.MEASUREMENTS
            if st.session_state.get(f"meas_{key}", "").strip()
        }
        values = {
            "brand": st.session_state.get("brand", ""),
            "item_type": st.session_state.get("item_type", ""),
            "size_tagged": st.session_state.get("size_tagged", ""),
            "color": st.session_state.get("color", ""),
            "material": st.session_state.get("material", ""),
            "origin": st.session_state.get("origin", ""),
            "condition": st.session_state.get("condition", ""),
            "flaws": st.session_state.get("flaws", ""),
            "style_era": st.session_state.get("style_era", ""),
            "gender_department": st.session_state.get("gender_department", ""),
        }
        confidence = {}
        for key, value in values.items():
            recorded = original_confidence.get(key, "none")
            if value.strip() and recorded == "none":
                confidence[key] = "user"
            else:
                confidence[key] = recorded or ("user" if value.strip() else "none")
        extracted = st.session_state.get("extracted_measurements") or {}
        if measurements and measurements == extracted:
            confidence["measurements"] = original_confidence.get("measurements", "high")
        elif measurements:
            confidence["measurements"] = "user"
            original_flags.pop("measurements", None)
        else:
            confidence["measurements"] = original_confidence.get("measurements", "none")
        return ClothingItem(
            measurements=measurements,
            cost_basis=Money.require_positive(Money.parse(st.session_state.get("cost_basis")), "Cost basis"),
            target_price=Money.require_positive(Money.parse(st.session_state.get("target_price")), "Target asking price"),
            buyer_paid_shipping=Money.require_positive(
                Money.parse(st.session_state.get("buyer_paid_shipping")), "Buyer-paid shipping"
            ),
            sales_tax=Money.require_positive(Money.parse(st.session_state.get("sales_tax")), "Sales tax"),
            field_flags=original_flags,
            field_confidence=confidence,
            review_notes=list(st.session_state.get("review_notes") or []),
            facebook_fulfillment=FacebookFulfillment.normalize(st.session_state.get("facebook_fulfillment")),
            **values,
        )

    @staticmethod
    def _listings() -> None:
        document = st.session_state.get("listings_doc")
        if not document:
            return
        st.subheader("Drafts")
        st.caption(
            f"Export {document['schema_version']} · {document['item_id']} · "
            "validated against schema/listing.v1.schema.json. Copy it into the marketplace yourself."
        )
        rows = []
        for platform in Platforms.ORDER:
            listing = document["listings"][platform]
            fees = listing["fees"]
            rows.append(
                {
                    "Platform": listing["display_name"],
                    "List price": ListingApp._money_cell(listing["price"]),
                    "Fees": "—" if fees is None else ListingApp._money_cell(fees["total"]),
                    "You net": ListingApp._money_cell(listing["net"]),
                }
            )
        st.dataframe(rows, width="stretch", hide_index=True)
        tabs = st.tabs([document["listings"][name]["display_name"] for name in Platforms.ORDER])
        for tab, platform in zip(tabs, Platforms.ORDER):
            with tab:
                ListingApp._platform(document["listings"][platform])
        payload = ListingExport.dumps(document)
        csv_payload = ListingExport.to_csv(document)
        left, right = st.columns(2)
        with left:
            st.download_button(
                "Download JSON",
                data=payload,
                file_name=f"listing-{document['item_id']}.json",
                mime="application/json",
            )
        with right:
            st.download_button(
                "Download CSV",
                data=csv_payload,
                file_name=f"listing-{document['item_id']}.csv",
                mime="text/csv",
            )

    @staticmethod
    def _platform(listing: dict) -> None:
        st.markdown(f"**Title** · {len(listing['title'])} / {listing['title_limit']}")
        st.code(listing["title"], language=None)
        ListingApp._copy("Copy title", listing["title"])
        price_cols = st.columns(3)
        price_cols[0].metric("List price", ListingApp._money_cell(listing["price"]))
        fee_total = None if listing["fees"] is None else listing["fees"]["total"]
        price_cols[1].metric("Fees", ListingApp._money_cell(fee_total))
        price_cols[2].metric("You net", ListingApp._money_cell(listing["net"]))
        st.markdown(listing["price_rationale"])
        if listing["fees"] is not None:
            st.markdown("**How the fee was computed**")
            st.write(listing["fees"]["formula"])
            for note in listing["fees"]["notes"]:
                st.caption(note)
        if listing["equalized_note"]:
            st.info(listing["equalized_note"])
        st.markdown(f"**Category** · {listing['category_suggestion']}")
        if listing["category_note"]:
            st.caption(listing["category_note"])
        if listing["item_specifics"]:
            st.markdown("**Item specifics**")
            st.dataframe(
                [{"Field": key, "Value": value} for key, value in listing["item_specifics"].items()],
                width="stretch",
                hide_index=True,
            )
        if listing["missing_specifics"]:
            st.caption("Add if you know them: " + ", ".join(listing["missing_specifics"]))
        if listing["tags"]:
            st.markdown(f"**{listing['tags_label']}**")
            st.write("  ".join(listing["tags"]))
        st.markdown(f"**Description** · {len(listing['description'])} / {listing['description_limit']}")
        st.code(listing["description"], language=None)
        ListingApp._copy("Copy description", listing["description"])
        st.markdown("**Before you post**")
        for line in listing["checklist"]:
            st.write("• " + line)

    @staticmethod
    def _money_cell(value: str | None) -> str:
        if not value:
            return "—"
        return f"${value}"

    @staticmethod
    def _copy(label: str, text: str) -> None:
        import hashlib

        payload = json.dumps(text).replace("<", "\\u003c")
        element_id = "copy-" + hashlib.sha1(f"{label}:{text}".encode()).hexdigest()[:12]
        st.html(
            f"""
            <button id="{element_id}" style="background:#0f6e56;color:#f6f1e8;border:0;border-radius:8px;padding:8px 12px;font:600 14px Outfit,sans-serif;cursor:pointer;">{label}</button>
            <span id="{element_id}-msg" style="margin-left:8px;font:13px Outfit,sans-serif;color:#0f6e56;"></span>
            <script>
              (() => {{
                const text = {payload};
                const btn = document.getElementById("{element_id}");
                if (!btn) return;
                btn.addEventListener("click", () => {{
                  const area = document.createElement("textarea");
                  area.value = text;
                  document.body.appendChild(area);
                  area.select();
                  let ok = false;
                  try {{ ok = document.execCommand("copy"); }} catch (e) {{ ok = false; }}
                  document.body.removeChild(area);
                  const msg = document.getElementById("{element_id}-msg");
                  if (msg) msg.textContent = ok ? "Copied" : "Use the code block copy icon";
                }});
              }})();
            </script>
            """,
            unsafe_allow_javascript=True,
        )
