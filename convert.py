"""
A Python 3 Markdown to DITA concept conversion tool

Uses md2py to obtain the nested structure
and markdown2dita (based on mistune) to convert
individual elements.

Change the output of individual elements (except for titles)
in markdown2dita."""

import md2py
import markdown2dita
import sys
import re

ditaRenderer = markdown2dita.Markdown()

# Placeholder for single # that we want to keep without being considered
# in the parse tree
hashSubs = "@@H1@@"

# Preamble and DTD declaration
declaration = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE concept PUBLIC "-//OASIS//DTD DITA Concept//EN" "concept.dtd">"""


def main():
    parsed_args = markdown2dita._parse_args(sys.argv[1:])

    # Read the input file specified, fall back to stdin or raise an error
    if parsed_args.input_file:
        original = open(parsed_args.input_file, 'r').read()
    elif not sys.stdin.isatty():
        original = ''.join(line for line in sys.stdin)
    else:
        print('No input file specified and unable to read input on stdin.\n'
              "Use the '-h' or '--help' flag to see usage information")
        exit(1)

    def check_sanity(text):
        if "######" in text:
            sys.exit("""You have headings that are lower than h4.
Promote these headings to h4 or above and try again.""")
        else:
            return text

    def strip_h1(input):
        # Strip out single # in comments
        input = "\n" + input
        output = re.sub(r"([^#])#([^#])", r"\1%s\2" % hashSubs, input)
        output = re.sub(r"%s" % hashSubs, r"#", output, 1)
        return output

    def restore_h1(input):
        # Restore any # signs we removed
        output = re.sub(r"%s" % hashSubs, r"#", input)
        return output

    # Check we don't have too many levels and replace the unwanted #s
    textInput = strip_h1(check_sanity(original))

    # Create a parse tree from the sanitized input
    toc = md2py.md2py(textInput)

    def get_concept_title_and_content(heading, inputMD=textInput):
        # Extract the heading and find all the text after it in the
        # sanitized markdown until the next # or the end of the file
        heading.title = str(heading)
        heading.content = "\n".join(re.findall(r"%s([^#]*)" % str(heading),
                                    inputMD))

    def start_concept_dita(heading):
        heading.dita = """
<concept id="{0}">
<title>{1}</title>
<conbody>
{2}</conbody>""".format(heading.title.lower().replace(" ", "_"),
                        heading.title,
                        ditaRenderer(heading.content))

    def end_concept_dita(heading):
        heading.dita += """\n</concept>"""

    def create_dita_from_topic(input):
        # There should only be one h1, so simplify by assuming that.
        # Walk down the tree as far as h4 (the maximum allowed)
        get_concept_title_and_content(toc.h1)
        start_concept_dita(toc.h1)
        for h2 in toc.h1.h2s:
            h2_index = list(toc.h1).index(h2)
            get_concept_title_and_content(h2)
            start_concept_dita(h2)
            for h3 in toc.h1[h2_index].h3s:
                h3_index = list(toc.h1[h2_index]).index(h3)
                get_concept_title_and_content(h3)
                start_concept_dita(h3)
                for h4 in toc.h1[h2_index][h3_index].h4s:
                    get_concept_title_and_content(h4)
                    start_concept_dita(h4)
                    end_concept_dita(h4)
                    h3.dita += h4.dita
                end_concept_dita(h3)
                h2.dita += h3.dita
            end_concept_dita(h2)
            toc.h1.dita += h2.dita
        end_concept_dita(toc.h1)
        return toc.h1.dita

    def create_final_dita(declaration, input):
        # Create the final concept DITA file

        def create_shortdesc(input):
            # Change the first paragraph to a short description, adjusting
            # the position of the first conbody
            result = re.sub(r"<conbody>[\s]*?<p>", r"<shortdesc>", input, 1)
            result = re.sub(r"</p>", r"</shortdesc>\n<conbody>", result, 1)
            return result

        dita = declaration + create_shortdesc(restore_h1(input))
        return dita

    interimDita = create_dita_from_topic(textInput)

    finalDita = create_final_dita(declaration, interimDita)

    # Write to the output file specified, or otherwise print to stdout
    if parsed_args.output_file:
        with open(parsed_args.output_file, 'w') as output_file:
            output_file.write(finalDita)
    else:
        print(finalDita)


if __name__ == '__main__':
    main()
