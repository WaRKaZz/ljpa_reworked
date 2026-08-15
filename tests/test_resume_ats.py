import os
import tempfile

from ljpa_reworked.models.crewai_pydantic_models import (
    CertificationCrewAI,
    EducationCrewAI,
    ExperienceCrewAI,
    PersonalInfoCrewAI,
    ResumeCrewAI,
    SkillCrewAI,
)
from ljpa_reworked.services.rendercv_helper import (
    convert_resume_crewai_to_rendercv_input,
    render_resume_crewai_to_pdf,
    validate_pdf_page_layout,
)


def sample_resume_data() -> ResumeCrewAI:
    return ResumeCrewAI(
        personal_info=PersonalInfoCrewAI(
            name="Ivan Danilov",
            email="ivan.danilov.wk@gmail.com",
            phone="+7 701 724 25 32",
            address="Karaganda, Kazakhstan",
            location="Karaganda, Kazakhstan",
            linkedin_url="https://www.linkedin.com/in/ivan-danilov-wk",
            target_title="Controls Engineer | PLC / SCADA / DCS | Industrial Automation",
        ),
        summary=(
            "Controls Engineer and Industrial Automation Specialist with over 7 years of "
            "experience in PLC, SCADA, and DCS systems across oil and gas, mining, and "
            "industrial infrastructure. Specialized in control system design, troubleshooting, "
            "FAT/SAT, commissioning, industrial networks, process automation, and process optimization."
        ),
        education=[
            EducationCrewAI(
                course="Master's Degree, Automation and Control",
                institution="Karagandy Technical University",
                location="Karaganda, Kazakhstan",
                start_date="2013",
                end_date="2019",
            )
        ],
        experience=[
            ExperienceCrewAI(
                title="FGP PLC Engineer",
                company="Tengizchevroil",
                location="Atyrau Region, Kazakhstan",
                start_date="2021-04",
                end_date="present",
                description=[
                    "Commissioned and functionally verified 350+ HVAC PLC control systems, 20+ GL150 adjustable-speed-drive PLC systems, and 10+ facility PLC systems.",
                    "Reduced unplanned downtime by 30%+ through control system diagnostic troubleshooting, logic optimization, and proactive maintenance.",
                    "Executed pre-commissioning, FAT, SAT, loop testing, and PAS network specification reviews for major oil and gas infrastructure.",
                ],
            ),
            ExperienceCrewAI(
                title="DCS Engineer",
                company="KAZ Minerals LLP",
                location="Shiderty, Kazakhstan",
                start_date="2019-12",
                end_date="2021-04",
                description=[
                    "Designed, tested, and deployed PLC/SCADA control logic modifications across Allen-Bradley ControlLogix, ABB System 800xA, and Siemens S7-1500 platforms.",
                    "Improved plant uptime by resolving complex PLC/SCADA/HMI communication faults and refining ladder/ST logic loops.",
                    "Managed process control maintenance documentation, incident investigations, PHA/JSA safety compliance, and MOC approvals.",
                ],
            ),
            ExperienceCrewAI(
                title="Automation Engineer",
                company="Example Industrial Systems Ltd.",
                location="Karaganda, Kazakhstan",
                start_date="2017-08",
                end_date="2019-12",
                description=[
                    "Developed Siemens S7-1200/1500 PLC ladder logic and WinCC SCADA systems for municipal water supply and flow-metering operations.",
                    "Engineered control cabinet designs and technical/commercial proposals with ROI payback analysis for industrial automation projects.",
                    "Installed, commissioned, and field-tested remote telemetry automation units communicating over Modbus TCP/IP.",
                ],
            ),
        ],
        skills=[
            SkillCrewAI(
                title="Control Systems & DCS",
                elements=[
                    "Distributed Control System (DCS)",
                    "PLC Programming",
                    "SCADA / HMI",
                    "Process Control",
                    "Control System Design",
                    "Process Optimization",
                ],
            ),
            SkillCrewAI(
                title="PLC & Automation Platforms",
                elements=[
                    "Allen-Bradley ControlLogix",
                    "CompactLogix",
                    "Studio 5000",
                    "Siemens S7-1200/S7-1500",
                    "TIA Portal",
                    "WinCC",
                    "ABB System 800xA",
                    "Beckhoff TwinCAT 3",
                    "Schneider Electric",
                    "Emerson",
                ],
            ),
            SkillCrewAI(
                title="Industrial Networks & Protocols",
                elements=[
                    "Modbus TCP/IP",
                    "Profinet",
                    "EtherCAT",
                    "BACnet",
                    "TCP/IP",
                    "HART",
                    "CAN",
                    "MQTT",
                ],
            ),
            SkillCrewAI(
                title="Engineering & Commissioning",
                elements=[
                    "FAT / SAT",
                    "Loop Testing",
                    "Commissioning",
                    "System Integration",
                    "Troubleshooting",
                    "IEC 61131-3",
                    "Python",
                    "MOC / JSA / PHA",
                ],
            ),
        ],
        projects=[],
        certifications=[
            CertificationCrewAI(
                title="Studio 5000 ControlLogix Fundamentals & Troubleshooting (CCP299)",
                issuer="Rockwell Automation",
                date="2022",
            ),
            CertificationCrewAI(
                title="TwinCAT 3 (Specialized)",
                issuer="Beckhoff Automation",
                date="2022",
            ),
            CertificationCrewAI(
                title="SIMATIC S7 Programming (ST-7PRО1)",
                issuer="Siemens",
                date="2022",
            ),
        ],
    )


def test_personal_info_target_title():
    resume = sample_resume_data()
    assert (
        resume.personal_info.target_title
        == "Controls Engineer | PLC / SCADA / DCS | Industrial Automation"
    )


def test_convert_resume_crewai_to_rendercv_headline():
    resume = sample_resume_data()
    rendercv_dict = convert_resume_crewai_to_rendercv_input(resume)
    cv = rendercv_dict["cv"]
    assert "headline" in cv
    assert (
        cv["headline"]
        == "Controls Engineer | PLC / SCADA / DCS | Industrial Automation"
    )


def test_convert_resume_crewai_certifications_formatting():
    resume = sample_resume_data()
    rendercv_dict = convert_resume_crewai_to_rendercv_input(resume)
    certifications = rendercv_dict["cv"]["sections"]["Certifications"]
    assert len(certifications) == 3
    assert certifications[0]["issuer"] == "Rockwell Automation"
    assert (
        certifications[0]["name"]
        == "Studio 5000 ControlLogix Fundamentals & Troubleshooting (CCP299)"
    )
    assert certifications[0]["date"] == "2022"


def test_render_pdf_layout():
    resume = sample_resume_data()
    with tempfile.TemporaryDirectory() as tmpdir:
        output_pdf = os.path.join(tmpdir, "test_resume.pdf")
        rendered_path = render_resume_crewai_to_pdf(resume, output_pdf)
        assert os.path.exists(rendered_path)
        is_valid, msg = validate_pdf_page_layout(rendered_path)
        assert is_valid, f"Layout validation failed: {msg}"
