import json

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

from .constants import FULL_COLUMN_WIDTH
from .constants.resume_constants import (
    CONTACT_PARAGRAPH_STYLE,
    NAME_PARAGRAPH_STYLE,
    RESUME_ELEMENTS_ORDER,
)
from .elements.resume_certification import Certification
from .elements.resume_education import Education
from .elements.resume_experience import Experience
from .elements.resume_project import Project
from .elements.resume_skill import Skill
from .elements.resume_summary import Summary
from .sections.resume_section import Section


class ResumeGenerator:
    def __init__(self, resume_data_json: dict):
        """
        Initializes the ResumeGenerator with resume data.
        :param resume_data_json: A dictionary containing resume data,
                                 typically loaded from a JSON file.
        """
        if isinstance(resume_data_json, str):
            self.data = json.loads(resume_data_json)
        else:
            self.data = resume_data_json

        personal_info = self.data.get("personal_info", {})
        self.author = personal_info.get("name", "Anonymous")
        self.email = personal_info.get("email", "email@example.com")
        self.address = personal_info.get("address", "City, Country")
        self.phone = personal_info.get("phone", "+1234567890")

    def _get_education_element(self, element) -> Education:
        e = Education()
        e.set_institution(element.get("institution", ""))
        e.set_course(element.get("course", ""))
        e.set_location(element.get("location", ""))
        e.set_start_date(element.get("start_date", ""))
        e.set_end_date(element.get("end_date", ""))
        return e

    def _get_experience_element(self, element) -> Experience:
        e = Experience()
        e.set_company(element.get("company", ""))
        e.set_title(element.get("title", ""))
        e.set_location(element.get("location", ""))
        e.set_start_date(element.get("start_date", ""))
        e.set_end_date(element.get("end_date", ""))
        e.set_description(element.get("description", []))
        return e

    def _get_project_element(self, element) -> Project:
        e = Project()
        e.set_title(element.get("title", ""))
        e.set_description(element.get("description", ""))
        e.set_link(element.get("link", ""))
        return e

    def _get_skills_element(self, element) -> Skill:
        e = Skill()
        e.set_title(element.get("title", ""))
        e.set_elements(element.get("elements", []))
        return e

    def _get_certification_element(self, element) -> Certification:
        e = Certification()
        e.set_title(element.get("title", ""))
        return e

    def generate(self, output_file_path: str) -> None:
        """
        Generates the resume as a PDF file.
        :param output_file_path: The path to save the generated PDF file.
        """
        resume_doc = SimpleDocTemplate(
            output_file_path,
            pagesize=A4,
            showBoundary=0,
            leftMargin=0.5 * inch,
            rightMargin=0.5 * inch,
            topMargin=0.2 * inch,
            bottomMargin=0.1 * inch,
            title=f"Resume of {self.author}",
            author=self.author,
        )

        table_data = []
        running_row_index = [0]
        table_styles = [
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (1, 0), 6),
        ]

        # Prepare data sections
        education_elements = [
            self._get_education_element(e) for e in self.data.get("education", [])
        ]
        experience_elements = [
            self._get_experience_element(e) for e in self.data.get("experience", [])
        ]
        project_elements = [
            self._get_project_element(e) for e in self.data.get("projects", [])
        ]
        skill_elements = [
            self._get_skills_element(e) for e in self.data.get("skills", [])
        ]
        certification_elements = [
            self._get_certification_element(e)
            for e in self.data.get("certifications", [])
        ]
        summary_elements = [Summary(description=self.data.get("summary", ""))]

        resume_data_sections = {}
        if skill_elements:
            resume_data_sections["skills"] = Section("Skills", skill_elements)
        if project_elements:
            resume_data_sections["projects"] = Section("Projects", project_elements)
        if experience_elements:
            resume_data_sections["experience"] = Section(
                "Experience", experience_elements
            )
        if education_elements:
            resume_data_sections["education"] = Section("Education", education_elements)
        if certification_elements:
            resume_data_sections["certifications"] = Section(
                "Certifications", certification_elements
            )
        if summary_elements:
            resume_data_sections["summary"] = Section("Summary", summary_elements)

        # Header
        table_data.append([Paragraph(self.author, NAME_PARAGRAPH_STYLE)])
        running_row_index[0] += 1

        table_data.append(
            [
                Paragraph(
                    f"{self.email} | {self.phone} | {self.address}",
                    CONTACT_PARAGRAPH_STYLE,
                ),
            ]
        )
        table_styles.append(
            ("BOTTOMPADDING", (0, running_row_index[0]), (1, running_row_index[0]), 1)
        )
        running_row_index[0] += 1

        # Sections
        for element_key in RESUME_ELEMENTS_ORDER:
            if element_key in resume_data_sections:
                section = resume_data_sections[element_key]
                section_table = section.get_section_table(
                    running_row_index, table_styles
                )
                table_data.extend(section_table)

        # Build the resume
        table = Table(
            table_data,
            colWidths=[FULL_COLUMN_WIDTH * 0.7, FULL_COLUMN_WIDTH * 0.3],
            spaceBefore=0,
            spaceAfter=0,
        )
        table.setStyle(TableStyle(table_styles))

        resume_elements = [table]
        resume_doc.build(resume_elements)
