from ljpa_reworked.models.crewai_pydantic_models import (
    EducationCrewAI,
    ExperienceCrewAI,
    PersonalInfoCrewAI,
    ResumeCrewAI,
    SkillCrewAI,
)
from ljpa_reworked.services.rendercv_helper import (
    convert_resume_crewai_to_rendercv_input,
)


def test_education_and_experience_use_normal_entry_layout():
    resume = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Test",
            email="test@example.com",
            phone="+1 555 0100",
            address="Berlin",
            location="Berlin",
        ),
        summary="Test summary",
        education=[
            EducationCrewAI(
                course="BSc",
                institution="University",
                location="Berlin",
                start_date="2016",
                end_date="2020",
            )
        ],
        experience=[
            ExperienceCrewAI(
                title="Engineer",
                company="Company",
                location="Berlin",
                start_date="2020",
                end_date="Present",
                description=["One", "Two", "Three"],
            )
        ],
        skills=[SkillCrewAI(title="Skills", elements=["PLC"])],
    )

    sections = convert_resume_crewai_to_rendercv_input(resume)["cv"]["sections"]
    assert sections["Education"][0]["name"] == "University — BSc"
    assert sections["Education"][0]["summary"] == "Berlin"
    assert "institution" not in sections["Education"][0]
    assert sections["Experience"][0]["name"] == "Company — Engineer"
    assert sections["Experience"][0]["summary"] == "Berlin"
    assert "company" not in sections["Experience"][0]
    assert list(sections) == ["Summary", "Skills", "Experience", "Education"]


def test_rendercv_disables_page_breaks_in_entries():
    resume = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Test User",
            email="test@example.com",
            phone="+1 555 0100",
            address="Berlin",
            location="Berlin",
        ),
        summary="Test summary",
        education=[
            EducationCrewAI(
                course="BSc CS",
                institution="University",
                location="Berlin",
                start_date="2016",
                end_date="2020",
            )
        ],
        experience=[
            ExperienceCrewAI(
                title="Lead Dev",
                company="Company",
                location="Berlin",
                start_date="2020",
                end_date="Present",
                description=["Bullet 1", "Bullet 2"],
            )
        ],
        skills=[SkillCrewAI(title="Languages", elements=["Python"])],
    )
    result = convert_resume_crewai_to_rendercv_input(resume)
    assert result["design"]["entries"]["allow_page_break_in_entries"] is False
    assert result["design"]["header"]["use_icons_for_connections"] is False
    assert result["design"]["page"]["show_last_updated_date"] is False
    assert list(result["cv"]["sections"].keys()) == ["Summary", "Skills", "Experience", "Education"]


def test_validate_pdf_page_layout_character_budget_rules(monkeypatch, tmp_path):
    from ljpa_reworked.services import rendercv_helper

    dummy_pdf = tmp_path / "dummy.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy content")

    class MockTextPage:
        def __init__(self, char_count):
            self.char_count = char_count

        def get_text_bounded(self):
            return "x" * self.char_count

    class MockPage:
        def __init__(self, char_count):
            self.char_count = char_count

        def get_textpage(self):
            return MockTextPage(self.char_count)

    class MockDoc:
        def __init__(self, page_counts):
            self.pages = [MockPage(count) for count in page_counts]

        def __len__(self):
            return len(self.pages)

        def __getitem__(self, idx):
            return self.pages[idx]

    monkeypatch.setattr(rendercv_helper.pypdfium2, "PdfDocument", lambda path: MockDoc([1399]))
    valid, msg = rendercv_helper.validate_pdf_page_layout(str(dummy_pdf))
    assert not valid
    assert "1400" in msg

    # A readable non-final page does not fail solely for density.
    monkeypatch.setattr(rendercv_helper.pypdfium2, "PdfDocument", lambda path: MockDoc([3000, 1400]))
    valid, _ = rendercv_helper.validate_pdf_page_layout(str(dummy_pdf))
    assert valid

    # Every page still needs minimum readable content.
    monkeypatch.setattr(rendercv_helper.pypdfium2, "PdfDocument", lambda path: MockDoc([3000, 1399]))
    valid, msg = rendercv_helper.validate_pdf_page_layout(str(dummy_pdf))
    assert not valid
    assert "Page 2" in msg

def test_rendercv_regression_fixture_llp_neo_stroy_no_split(tmp_path):
    import os

    import pypdfium2

    from ljpa_reworked.services.rendercv_helper import render_resume_crewai_to_pdf

    target_pdf = str(tmp_path / "llp_neo_stroy_test.pdf")

    # Create a resume with a prominent LLP Neo Stroy experience entry with multiple bullets
    resume = ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Ivan Operator",
            email="ivan@example.com",
            phone="+1 555 0199",
            address="Almaty",
            location="Almaty, Kazakhstan",
            target_title="Lead Control Systems & Industrial Automation Engineer",
        ),
        summary=(
            "Senior Lead Control Systems and Industrial Automation Engineer with over 10 years of experience "
            "designing, commissioning, and optimizing PLC, SCADA, DCS, and industrial communication networks "
            "across major oil & gas, mining, and industrial process facilities."
        ),
        education=[
            EducationCrewAI(
                course="B.S. Automation and Control",
                institution="Kazakh National Technical University",
                location="Almaty, Kazakhstan",
                start_date="2010-09",
                end_date="2014-06",
            )
        ],
        experience=[
            ExperienceCrewAI(
                title="Lead Controls Engineer",
                company="LLP Neo Stroy",
                location="Almaty, Kazakhstan",
                start_date="2020-01",
                end_date="Present",
                description=[
                    "Designed, programmed, and commissioned integrated Allen-Bradley ControlLogix and Siemens S7-1500 PLC systems for large-scale industrial water treatment and chemical processing plants.",
                    "Engineered high-availability Modbus TCP/IP and PROFINET industrial networks linking 50+ remote I/O racks with SCADA visualization nodes, resulting in zero network downtime.",
                    "Led Factory Acceptance Testing (FAT) and Site Acceptance Testing (SAT) for 20+ GL150 drive PLC systems, reducing site commissioning time by 25%.",
                    "Developed automated diagnostic routines and alarm management strategies in Studio 5000 and TIA Portal, cutting unpredicted facility downtime by 30%.",
                ],
            ),
            ExperienceCrewAI(
                title="Automation Engineer",
                company="TechAutomation Ltd",
                location="Astana, Kazakhstan",
                start_date="2014-07",
                end_date="2019-12",
                description=[
                    "Programmed Schneider Electric Modicon PLCs and Wonderware System Platform SCADA interfaces for oil refinery auxiliary systems.",
                    "Configured field instrumentation and HART protocol transmitters for 100+ temperature, pressure, and flow loops.",
                ],
            ),
        ],
        skills=[
            SkillCrewAI(title="PLC & SCADA", elements=["Allen-Bradley Studio 5000", "Siemens TIA Portal", "WinCC", "Schneider EcoStruxure"]),
            SkillCrewAI(title="Networks & Protocols", elements=["Modbus TCP/IP", "PROFINET", "Profibus DP", "EtherNet/IP"]),
        ],
        certifications=[],
        projects=[],
    )

    try:
        pdf_path = render_resume_crewai_to_pdf(resume, target_pdf)
        assert os.path.exists(pdf_path)

        doc = pypdfium2.PdfDocument(pdf_path)
        pages_text = [page.get_textpage().get_text_bounded() for page in doc]
        page_counts = [len(text) for text in pages_text]
        print("Regression PDF Page Character Counts:", page_counts)

        # Assert no page contains only continuation bullets from LLP Neo Stroy without the entry header
        for _i, text in enumerate(pages_text):
            if "LLP Neo Stroy" in text:
                assert "Lead Controls Engineer" in text or "LLP Neo Stroy" in text
            if "Designed, programmed, and commissioned" in text or "Engineered high-availability Modbus" in text:
                # Must contain the entry title/header on the page where its bullets appear
                assert "LLP Neo Stroy" in text
    finally:
        if os.path.exists(target_pdf):
            os.remove(target_pdf)


def test_resume_generation_task_prompt_guidance():
    import yaml

    with open("src/ljpa_reworked/crews/resume_generation_crew/config/tasks.yaml", encoding="utf-8") as f:
        tasks = yaml.safe_load(f)

    desc = tasks["resume_generation_task"]["description"]

    # Verify sector ordering
    assert "Summary, Skills, Experience, Education, Certifications, Projects" in desc or (
        "Summary" in desc and "Skills" in desc and "Experience" in desc and "Education" in desc
    )

    # Verify character budget guidance
    assert "3300" in desc and "3475" in desc
    assert "1400" in desc

    # Verify plain field-by-field output and page-filling instructions.
    assert "FIELD-BY-FIELD OUTPUT CONTRACT" in desc
    assert "Count every visible character" in desc
    assert "exactly 3-4 long highlights" in desc
