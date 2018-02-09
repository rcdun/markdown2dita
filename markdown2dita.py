# coding: utf-8
"""
    markdown2dita
    ~~~~~~~~~~~~~
    A markdown to dita-ot conversion tool written in pure python.

    Uses mistune to parse the markdown.
"""
from __future__ import print_function

import argparse
import sys

import mistune
import re

__version__ = '0.3'
__author__ = 'Matt Carabine <matt.carabine@gmail.com>'
__all__ = ['Renderer', 'Markdown', 'markdown', 'escape']


# Defining a custom renderer
class Renderer(mistune.Renderer):

    def codespan(self, text):
        return '<codeph>{0}</codeph>'.format(escape(text.rstrip()))

    def link(self, link, title, content):
        return '<xref href="{0}">{1}</xref>'.format(link, escape(content or title))

    def block_code(self, code, language=None):
        code = escape(code.rstrip('\n'))
        if language:
            return ('<codeblock outputclass="language-{0}">{1}</codeblock>'
                    .format(language, code))
        else:
            return '<codeblock>{0}</codeblock>'.format(code)

    def block_quote(self, text):
        return '<codeblock>{0}</codeblock>'.format(text)

    def header(self, text, level, raw=None):
        # Dita only supports one title per section
        topic_title_level = self.options.get('title_level', 1)
        title_level = self.options.get('title_level', 2)
        if level == topic_title_level:
            return '{0}'.format(text)
        if level <= title_level:
            return '</section>\n<section>\n<title>{0}</title>\n'.format(text)
        else:
            return '<p><b>{0}</b></p>'.format(text)

    def double_emphasis(self, text):
        return '<b>{0}</b>'.format(text)

    def emphasis(self, text):
        return '<i>{0}</i>'.format(text)

    def hrule(self):
        # Dita has no horizontal rule, ignore it
        # could maybe divide sections?
        return ''

    def inline_html(self, text):
        # Dita does not support inline html, just pass it through
        return text

    def list_item(self, text):
        return '<li>{0}</li>\n'.format(text)

    def list(self, body, ordered=True):
        if ordered:
            return '<ol>{0}</ol>\n'.format(body)
        else:
            return '<ul>{0}</ul>\n'.format(body)

    def image(self, src, title, text):

        # Derived from the mistune library source code

        src = mistune.escape_link(src)
        text = escape(text, quote=True)
        if title:
            title = escape(title, quote=True)
            output = ('<fig><title>{0}</title>\n'
                      '<image href="{1}" alt="{2}"/></fig>'
                      .format(title, src, text))
        else:
            output = '<image href="{0}" alt="{1}"/>'.format(src, text)

        return output

    def table(self, header, body, cols):
        col_string = ['<colspec colname="col{0}"/>'.format(x+1)
                      for x in range(cols)]
        output_str = ('<table>\n<tgroup cols="{0}">\n{1}\n'
                      .format(cols, '\n'.join(col_string)))

        return (output_str + '<thead>\n' + header + '</thead>\n<tbody>\n' +
                body + '</tbody>\n</tgroup>\n</table>')

    def table_row(self, content):
        return '<row>\n{0}</row>\n'.format(content)

    def table_cell(self, content, **flags):
        align = flags['align']

        if align:
            return '<entry align="{0}">{1}</entry>\n'.format(align, content)
        else:
            return '<entry>{0}</entry>\n'.format(content)

    def autolink(self, link, is_email=False):
        text = link = escape(link)
        if is_email:
            link = 'mailto:{0}'.format(link)
        return '<xref href="{0}">{1}</xref>'.format(link, text)

    def footnote_ref(self, key, index):
        return ''

    def footnote_item(self, key, text):
        return ''

    def footnotes(self, text):
        return ''

    def strikethrough(self, text):
        return text


class Markdown(mistune.Markdown):

    def __init__(self, renderer=None, inline=None, block=None, **kwargs):
        if not renderer:
            renderer = Renderer(**kwargs)
        else:
            kwargs.update(renderer.options)

        super(Markdown, self).__init__(
            renderer=renderer, inline=inline, block=block)

    def parse(self, text, page_id='enter-id-here',
              title='Enter the page title here'):

        # Preamble and DTD declaration
        declaration = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE concept PUBLIC "-//OASIS//DTD DITA Concept//EN" "concept.dtd">
"""

        def split_text(input):
            # Apply a regex to split the file into:
            # 1 - title
            # 2 - conbody (up until the first ## heading)
            # 3 - everything else
            try:
                regex = r"(\s#.*)([\s\S]*?\n)(##[\s\S]*)"
                text_split = re.findall(regex, input)
                title = text_split[0][0]
                conbody = text_split[0][1]
                nested = text_split[0][2]
                return title, conbody, nested
            except IndexError:
                regex = r"(\s#.*)([\s\S]*)"
                text_split = re.findall(regex, input)
                title = text_split[0][0]
                conbody = text_split[0][1]
                nested = None
                return title, conbody, nested

        # Need to:
        # * Pick out first paragraph and use as <shortdesc>
        # * Replace <section> with <concept><conbody>
        # * Allow <concept> for h3 and h4, with proper nesting
        #   * header() already supports further levels, via title_level
        #   * need to get the nesting working - for loops?

        def process_conbody(text):
            text = super(Markdown, self).parse(text)
            if text.startswith('</section>'):
                text = text[10:]
            return text

        def process_nested(text):
            if text is None:
                return ""
            else:
                text = super(Markdown, self).parse(text) + '\n</section>\n'
                if text.startswith('</section>'):
                    text = text[10:]
                else:
                    text = '<section>\n' + text
                return text

        title, conbody, nested = split_text(text)
        title_output = super(Markdown, self).parse(title)
        conbody_output = process_conbody(conbody)
        nested_output = process_nested(nested)

        dita = declaration + """<concept xml:lang="en-us" id="{0}">
<title>{1}</title>
<shortdesc>Enter the short description for this page here</shortdesc>
<conbody>{2}{3}</conbody>
</concept>""".format((title_output.lower()).replace(" ", "_"), title_output, conbody_output, nested_output)
        return dita

    def output_table(self):

        # Derived from the mistune library source code
        aligns = self.token['align']
        aligns_length = len(aligns)

        cell = self.renderer.placeholder()

        # header part
        header = self.renderer.placeholder()
        cols = len(self.token['header'])
        for i, value in enumerate(self.token['header']):
            align = aligns[i] if i < aligns_length else None
            flags = {'header': True, 'align': align}
            cell += self.renderer.table_cell(self.inline(value), **flags)

        header += self.renderer.table_row(cell)

        # body part
        body = self.renderer.placeholder()
        for i, row in enumerate(self.token['cells']):
            cell = self.renderer.placeholder()
            for j, value in enumerate(row):
                align = aligns[j] if j < aligns_length else None
                flags = {'header': False, 'align': align}
                cell += self.renderer.table_cell(self.inline(value), **flags)
            body += self.renderer.table_row(cell)

        return self.renderer.table(header, body, cols)


def escape(text, quote=False, smart_amp=True):
    return mistune.escape(text, quote=quote, smart_amp=smart_amp)


def _parse_args(args):
    parser = argparse.ArgumentParser(description='markdown2dita - a markdown '
                                     'to dita-ot CLI conversion tool.')
    parser.add_argument('-i', '--input-file',
                        help='input markdown file to be converted.'
                             'If omitted, input is taken from stdin.')
    parser.add_argument('-o', '--output-file',
                        help='output file for the converted dita content.'
                             'If omitted, output is sent to stdout.')
    return parser.parse_args(args)


def markdown(text, escape=True, **kwargs):
    return Markdown(escape=escape, **kwargs)(text)


def main():
    parsed_args = _parse_args(sys.argv[1:])

    # Read the input file specified, fall back to stdin or raise an error
    if parsed_args.input_file:
        input_str = open(parsed_args.input_file, 'r').read()
    elif not sys.stdin.isatty():
        input_str = ''.join(line for line in sys.stdin)
    else:
        print('No input file specified and unable to read input on stdin.\n'
              "Use the '-h' or '--help' flag to see usage information",
              file=sys.stderr)
        exit(1)

    markdown = Markdown()
    dita_output = markdown(input_str)

    # Write to the output file specified, or otherwise print to stdout
    if parsed_args.output_file:
        with open(parsed_args.output_file, 'w') as output_file:
            output_file.write(dita_output)
    else:
        print(dita_output)


if __name__ == '__main__':
    main()
