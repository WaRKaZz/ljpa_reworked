from reportlab.platypus import Paragraph

from ..constants.resume_constants import JOB_DETAILS_PARAGRAPH_STYLE


class Summary:
    def __init__(self, description="") -> None:
        self.description = description

    def set_description(self, description: str) -> None:
        self.description = description

    def get_table_element(self, running_row_index: list, table_styles: list) -> list:
        table = []
        table.append(
            [
                Paragraph(
                    self.description,
                    style=JOB_DETAILS_PARAGRAPH_STYLE,
                ),
            ]
        )
        table_styles.append(
            ("TOPPADDING", (0, running_row_index[0]), (1, running_row_index[0]), 1)
        )
        table_styles.append(
            ("BOTTOMPADDING", (0, running_row_index[0]), (1, running_row_index[0]), 0)
        )
        table_styles.append(
            ("SPAN", (0, running_row_index[0]), (1, running_row_index[0]))
        )
        running_row_index[0] += 1
        return table