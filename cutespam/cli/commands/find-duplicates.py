import argparse

DESCRIPTION = "Finds duplicate image files and generates a html page showing them"

def main(ARGS):
    import webbrowser
    import os

    from PIL import Image

    from cutespam.xmpmeta import CuteMeta
    from cutespam.db import find_all_duplicates, picture_file_for_uid

    def html_output(duplicates):
        t_html = """
        <html>
            <head>
                <style>
                    table {{
                        table-layout: fixed;
                        border-bottom: 1px solid black;
                        width: 100%;
                        padding: 5px;
                    }}
                    img {{
                        max-width: 100%;
                        max-height: 500px;
                    }}
                    code {{
                        display: block;
                        white-space: pre-wrap;
                        word-wrap: break-word;
                    }}
                </style>
            </head>
            <body>
            {tables}
            </body>
        </html>
        """
        t_table = """
            <table>
                <tr>{images}</tr>
                <tr>{links}</tr>
                <tr>{dimensions}</tr>
                <tr>{tags}</tr>
            </table>
        """

        tables = ""
        for duplicate in duplicates:
            images = ""
            links = ""
            dimensions = ""
            tags = ""

            for uid in duplicate:
                d = picture_file_for_uid(uid)
                fsize = os.path.getsize(d.resolve()) / 1_000_000
                with Image.open(d) as img_data:
                    width, height = img_data.size
                    fformat = img_data.format

                meta = CuteMeta.from_db(uid)
                path = str(d.resolve().absolute())
                images += f"<td><img src='{path}'/></td>"
                links += f"<td><a href={path}><code>{path}</code></a></td>"
                dimensions += f"<td><code>Resolution: {width}x{height}\nFormat: {fformat}\nSize: {fsize:.2f} MB</code></td>"
                tags += f"<td><code>{meta.to_string()}</code></td>"

            tables += t_table.format(images = images, links = links, dimensions = dimensions, tags = tags)

        return t_html.format(tables = tables)

    duplicates = find_all_duplicates()

    if len(duplicates) > 0:
        res = html_output(duplicates)
        with open(ARGS.outf, "w") as file:
            file.write(res)
        webbrowser.open(ARGS.outf)
    else:
        print("No duplicates")

def args(parser):
    parser.add_argument("outf", help = "Output file")
    