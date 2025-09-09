# snippet_10_07.ipynb
import pathlib
from borb.pdf import (
    Document,
    FixedColumnWidthTable,
    Image,
    LayoutElement,
    Page,
    PageLayout,
    Paragraph,
    PDF,
    SingleColumnLayout,
    Standard14Fonts,
    Table,
    X11Color,
)

doc: Document = Document()

page: Page = Page()
doc.append_page(page)

layout: PageLayout = SingleColumnLayout(page)

# add company logo
layout.append_layout_element(
    Image(
        pathlib.Path("geekodnaranja-04.png"),
        size=(180, 200),
    )
)

# add invoice header
layout.append_layout_element(
    FixedColumnWidthTable(number_of_rows=5, number_of_columns=2)
    .append_layout_element(Paragraph("[Street Address]"))
    .append_layout_element(Paragraph("Date: 01/01/1970"))
    .append_layout_element(Paragraph("[City, State, ZIP Code]"))
    .append_layout_element(Paragraph("Invoice Nr: 00001"))
    .append_layout_element(Paragraph("[Phone]"))
    .append_layout_element(Paragraph("Due Date: 01/01/1970"))
    .append_layout_element(Paragraph("[Email]"))
    .append_layout_element(Paragraph(""))
    .append_layout_element(Paragraph("[Company Website]"))
    .append_layout_element(Paragraph(""))
    .set_padding_on_all_cells(
        padding_bottom=2, padding_left=2, padding_right=2, padding_top=2
    )
    .no_borders()
)

# add bill to / ship to
layout.append_layout_element(
    FixedColumnWidthTable(number_of_rows=5, number_of_columns=2)
    .append_layout_element(
        Paragraph(
            "BILL TO",
            padding_bottom=4,
            padding_left=2,
            padding_right=2,
            padding_top=2,
            font=Standard14Fonts.get("Helvetica-Bold"),
            background_color=X11Color.BLACK,
            font_color=X11Color.WHITE,
        )
    )
    .append_layout_element(
        Paragraph(
            "SHIP TO",
            padding_bottom=4,
            padding_left=2,
            padding_right=2,
            padding_top=2,
            font=Standard14Fonts.get("Helvetica-Bold"),
            background_color=X11Color.BLACK,
            font_color=X11Color.WHITE,
        )
    )
    .append_layout_element(Paragraph("[Recipient Name]"))
    .append_layout_element(Paragraph("[Recipient Name]"))
    .append_layout_element(Paragraph("[Street Address]"))
    .append_layout_element(Paragraph("[Street Address]"))
    .append_layout_element(Paragraph("[City, State, ZIP Code]"))
    .append_layout_element(Paragraph("[City, State, ZIP Code]"))
    .append_layout_element(Paragraph("[Phone]"))
    .append_layout_element(Paragraph("[Phone]"))
    .set_padding_on_all_cells(
        padding_bottom=2, padding_left=2, padding_right=2, padding_top=2
    )
    .no_borders()
)

# add items
layout.append_layout_element(
    FixedColumnWidthTable(
        number_of_rows=3, number_of_columns=4, column_widths=[2, 1, 1, 1]
    )
    .append_layout_element(
        Table.TableCell(
            Paragraph(
                "DESCRIPTION",
                padding_bottom=4,
                padding_left=2,
                padding_right=2,
                padding_top=2,
                font=Standard14Fonts.get("Helvetica-Bold"),
                font_color=X11Color.WHITE,
            ),
            background_color=X11Color.BLACK,
        )
    )
    .append_layout_element(
        Table.TableCell(
            Paragraph(
                "PRICE",
                padding_bottom=4,
                padding_left=2,
                padding_right=2,
                padding_top=2,
                font=Standard14Fonts.get("Helvetica-Bold"),
                font_color=X11Color.WHITE,
            ),
            background_color=X11Color.BLACK,
        )
    )
    .append_layout_element(
        Table.TableCell(
            Paragraph(
                "QUANTITY",
                padding_bottom=4,
                padding_left=2,
                padding_right=2,
                padding_top=2,
                font=Standard14Fonts.get("Helvetica-Bold"),
                font_color=X11Color.WHITE,
            ),
            background_color=X11Color.BLACK,
        )
    )
    .append_layout_element(
        Table.TableCell(
            Paragraph(
                "TOTAL",
                padding_bottom=4,
                padding_left=2,
                padding_right=2,
                padding_top=2,
                font=Standard14Fonts.get("Helvetica-Bold"),
                font_color=X11Color.WHITE,
            ),
            background_color=X11Color.BLACK,
        )
    )
    .append_layout_element(Paragraph("Mechanical Keyboard"))
    .append_layout_element(Paragraph("100"))
    .append_layout_element(Paragraph("3"))
    .append_layout_element(Paragraph("300"))
    .append_layout_element(Paragraph("USB-C Docking Station"))
    .append_layout_element(Paragraph("150"))
    .append_layout_element(Paragraph("1"))
    .append_layout_element(Paragraph("150"))
    .no_borders()
)




PDF.write(what=doc, where_to="output.pdf")
