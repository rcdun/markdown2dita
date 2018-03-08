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
import argparse

ditaRenderer = markdown2dita.Markdown()

# Placeholder for single # that we want to keep without being considered
# in the parse tree and for placeholder for disambiguating headings
hashSubs = "@@H1@@"
headingSub = "_@@!!£"
invalid_heading_status = False

# Preamble and DTD declaration
declaration = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE concept PUBLIC "-//OASIS//DTD DITA Concept//EN" "concept.dtd">"""


def _parse_args(args):
    parser = argparse.ArgumentParser(description='convert + markdown2dita - a markdown '
                                     'to dita-ot CLI conversion tool.')
    parser.add_argument('-i', '--input-file',
                        help='input markdown file to be converted.'
                             'If omitted, input is taken from stdin.')
    parser.add_argument('-o', '--output-file',
                        help='output file for the converted dita content.'
                             'If omitted, output is sent to stdout.')
    parser.add_argument('-s', '--shortdesc',
                        help='Configures whether to add a shortdesc to the DITA. Default is yes')
    return parser.parse_args(args)

def main():
    parsed_args = _parse_args(sys.argv[1:])

    # Read the input file specified, fall back to stdin or raise an error
    if parsed_args.input_file:
        original = open(parsed_args.input_file, 'r').read()
    elif not sys.stdin.isatty():
        original = ''.join(line for line in sys.stdin)
    else:
        print('No input file specified and unable to read input on stdin.\n'
              "Use the '-h' or '--help' flag to see usage information")
        exit(1)

    def sanitize(text):

        def strip_h1(text):
            # Replace any # (e.g. code comments) for h1s except
            # the first (for the title) with a substitute
            # Otherwise the conversion treats them as headings. 
            output = "\n" + text
            output = re.sub(r"([^#])#([^#])", r"\1%s\2" % hashSubs, output)
            output = re.sub(r"%s" % hashSubs, r"#", output, 1)
            return output

        def disambiguate_duplicate_headings(text, substitution=headingSub):
            idRegex = r'(#[\sA-Za-z0-9]*?)\n'
            list_of_ids = re.findall(idRegex, text)
            for match in list_of_ids:
                if list_of_ids.count(match) == 1:
                    list_of_ids.remove(match)
            duplicates = set(list_of_ids)
            for duplicate in duplicates:
                i = 1
                for match in list_of_ids:
                    if match == duplicate:
                        text = text.replace(match + "\n", match + substitution + str(i), 1)
                        i += 1
            return text

        if "######" in text:
            sys.exit("""You have headings that are lower than h4.
Promote these headings to h4 or above and try again.""")
        # Need to make this a better check - what if there's a h6 but no h5?
        # This + check_invalid_headings won't catch that

        text = disambiguate_duplicate_headings(strip_h1(text))
        return text

    def restore_headings(original, h1substituion=hashSubs, titleSubstitution=headingSub):
        # Restore any # signs we removed
        output = re.sub(r"%s" % hashSubs, r"#", original)
        # Fix any titles we altered to de-duplicate them
        output = re.sub(r"%s[\d]*?</title>" % titleSubstitution, r"</title>", output)
        return output

    # Check we don't have too many levels and replace the unwanted #s
    textInput = sanitize(original)

    # Create a parse tree from the sanitized input
    toc = md2py.md2py(textInput)

    def check_invalid_headings():
        # Check for jumps in the number of headings
        invalid_heading_status = False

        def check_heading(heading, invalid_headings):
            current_status = invalid_heading_status
            for invalid_heading in invalid_headings:
                if not list(getattr(heading, invalid_heading)) == []:
                    print("""Invalid heading jump:
One or more {0}s after {1}""".format(invalid_heading[:2], str(heading).split(headingSub)[0]))
                    current_status = True
            return current_status

        invalid_heading_status = check_heading(toc.h1, ['h3s', 'h4s', 'h5s'])
        for h2 in toc.h1.h2s:
            h2_index = list(toc.h1).index(h2)
            invalid_heading_status = check_heading(h2, ['h4s', 'h5s'])
            for h3 in toc.h1[h2_index].h3s:
                invalid_heading_status = check_heading(h3, ['h5s'])

        if invalid_heading_status is True:
            sys.exit("Invalid structure. Check your file and try again.")

    check_invalid_headings()

    def get_concept_title_and_content(heading, inputMD=textInput):
        # Extract the heading and find all the text after it in the
        # sanitized markdown until the next # or the end of the file
        heading.title = str(heading)
        heading.content = "\n".join(re.findall(r"#[\s]%s([^#]*)" % str(heading),
                                    inputMD))

    def start_concept_dita(heading):
        heading.dita = """
<concept id="{0}">
<title>{1}</title>
<conbody>
{2}</conbody>""".format(re.sub(r'\W+', '', heading.title.lower().replace(" ", "_")),
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

    def create_final_dita(declaration, input_dita):
        # Create the final concept DITA file

        def create_shortdesc(input_dita):
            # Change the first paragraph to a short description, adjusting
            # the position of the first conbody
            result = re.sub(r"<conbody>[\s]*?<p>", r"<shortdesc>", input_dita, 1)
            result = re.sub(r"</p>", r"</shortdesc>\n<conbody>", result, 1)
            return result

        def tidy_xml(input_dita):
            # Strip <p> tags around <fig>
            result = input_dita.replace("<p><fig>", "<fig>")
            result = result.replace("</fig></p>", "</fig>")
            # Remove any stray <p> with only special characters
            result = re.sub(r'<p>\W+</p>', '', result)
            return result

        dita = declaration + tidy_xml(restore_headings(input_dita))

        if parsed_args.shortdesc == "no":
            pass
        else:
            dita = create_shortdesc(dita)

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
