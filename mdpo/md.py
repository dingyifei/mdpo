"""Markdown related utilities for mdpo."""

import re

import md4c

from mdpo.po import po_escaped_string
from mdpo.text import min_not_max_chars_in_a_row


LINK_REFERENCE_RE = re.compile(
    r'^\s{0,3}\[([^\]]+)\]:\s+<?([^\s>]+)>?\s*["\'\(]?([^"\'\)]+)?',
)
LINK_REFERENCED_LINK_RE = re.compile(r'\[([^\]]+)\]\[([^\]\s]+)\]')


def escape_links_titles(text, link_start_string='[', link_end_string=']'):
    r"""Escapes ``"`` characters found inside link titles.

    This is used by mdpo extracting titles of links which contains Markdown
    `link titles <https://spec.commonmark.org/0.29/#link-title>`_ delimiter
    characters.

    Args:
        text (str): Text where the links titles to escape will be searched.
        link_start_string (str): String that delimites the start of a link.
        link_end_string (str): String that delimites the end of a link.

    Returns:
        str: Same text as input with escaped title delimiters characters found
        inside titles.

    Examples:
        >>> title = '[a link](href "title with characters to escape "")'
        >>> escape_links_titles(title)
        '[a link](href "title with characters to escape \\"")'
    """
    link_end_string_escaped_regex = re.escape(link_end_string)
    regex = re.compile(
        r'({}[^{}]+{}\([^\s]+\s)([^\)]+)'.format(
            re.escape(link_start_string),
            link_end_string_escaped_regex,
            link_end_string_escaped_regex,
        ),
    )

    for match in re.findall(regex, text):
        original_string = match[0] + match[1]
        target_string = match[0] + '"%s"' % (
            match[1][1:-1].replace('"', '\\"')
        )
        text = text.replace(original_string, target_string)
    return text


def parse_link_references(content):
    """Parses link references found in a Markdown content.

    Args:
        content (str): Markdown content to be parsed.

    Returns:
        list: Tuples with 3 values, target, href and title for each link
            reference.
    """
    response = []
    for line in content.splitlines():
        linestrip = line.strip()
        if linestrip and linestrip[0] == '[':
            match = re.search(LINK_REFERENCE_RE, linestrip)
            if match:
                response.append(match.groups())
    return response


class MarkdownSpanWrapper:
    __slots__ = {
        # arguments
        'width',
        'first_line_width',
        'indent',
        'first_line_indent',
        'md4c_extensions',

        'bold_start_string',
        'bold_end_string',
        'italic_start_string',
        'italic_start_string_escaped',
        'italic_end_string',
        'italic_end_string_escaped',
        'code_start_string',
        'code_start_string_escaped',
        'code_end_string',
        'code_end_string_escaped',
        'link_start_string',
        'link_end_string',
        'wikilink_start_string',
        'wikilink_end_string',

        # state
        'output',
        '_current_line',
        '_current_aspan_href',
        '_current_aspan_title',
        '_inside_codespan',
        '_current_wikilink_target',
    }

    def __init__(
        self,
        width=80,
        first_line_width=80,
        indent='',
        first_line_indent='',
        md4c_extensions={},
        **kwargs,
    ):
        self.width = width
        self.first_line_width = first_line_width
        self.indent = indent
        self.first_line_indent = first_line_indent
        self.md4c_extensions = md4c_extensions

        self.output = ''
        self._current_line = ''

        self.bold_start_string = kwargs.get('bold_start_string', '**')
        self.bold_end_string = kwargs.get('bold_end_string', '**')
        self.italic_start_string = kwargs.get('italic_start_string', '*')
        self.italic_end_string = kwargs.get('italic_end_string', '*')
        self.code_start_string = kwargs.get('code_start_string', '`')[0]
        self.code_end_string = kwargs.get('code_end_string', '`')[0]
        self.link_start_string = kwargs.get('link_start_string', '[')
        self.link_end_string = kwargs.get('link_end_string', ']')
        self.wikilink_start_string = kwargs.get('wikilink_start_string', '[[')
        self.wikilink_end_string = kwargs.get('wikilink_end_string', ']]')

        self.italic_start_string_escaped = kwargs.get(
            'italic_start_string_escaped',
            po_escaped_string(self.italic_start_string),
        )
        self.italic_end_string_escaped = kwargs.get(
            'italic_end_string_escaped',
            po_escaped_string(self.italic_end_string),
        )
        self.code_start_string_escaped = kwargs.get(
            'code_start_string_escaped',
            po_escaped_string(self.code_start_string),
        )
        self.code_end_string_escaped = kwargs.get(
            'code_end_string_escaped',
            po_escaped_string(self.code_end_string),
        )

        self._current_aspan_href = None
        self._current_aspan_title = None
        self._inside_codespan = False
        self._current_wikilink_target = None

    def _get_currently_applied_width(self):
        return self.width if self.output else self.first_line_width

    def _get_currently_applied_indent(self):
        return self.indent if self.output else self.first_line_indent

    def enter_block(self, block, details):
        pass

    def leave_block(self, block, details):
        pass

    def enter_span(self, span, details):
        if span is md4c.SpanType.CODE:
            self._inside_codespan = True
            self._current_line += self.code_start_string
        elif span is md4c.SpanType.A:
            self._current_line += self.link_start_string
            self._current_aspan_href = details['href'][0][1]
            self._current_aspan_title = (
                details['title'][0][1] if details['title'] else None
            )
        elif span is md4c.SpanType.STRONG:
            self._current_line += self.bold_start_string
        elif span is md4c.SpanType.EM:
            self._current_line += self.italic_start_string
        elif span is md4c.SpanType.WIKILINK:
            self._current_line += self.wikilink_start_string
            self._current_wikilink_target = details['target'][0][1]
        elif span is md4c.SpanType.IMG:
            self._current_line += '!['

    def leave_span(self, span, details):
        if span is md4c.SpanType.CODE:
            self._inside_codespan = False
            self._current_line += self.code_end_string
        elif span is md4c.SpanType.A:
            if self._current_line[-1] != '>':
                self._current_line += f']({self._current_aspan_href}'
                if self._current_aspan_title:
                    self._current_line += (
                        f' "{escape_links_titles(self._current_aspan_title)}"'
                    )
                self._current_line += ')'
            self._current_aspan_href = False
            self._current_aspan_href = None
            self._current_aspan_title = None
        elif span is md4c.SpanType.STRONG:
            self._current_line += self.bold_end_string
        elif span is md4c.SpanType.EM:
            self._current_line += self.italic_end_string
        elif span is md4c.SpanType.WIKILINK:
            self._current_line += self.wikilink_end_string
            self._current_wikilink_target = None
        elif span is md4c.SpanType.IMG:
            src = details['src'][0][1]
            self._current_line += f']({src}'
            if details['title']:
                title = details['title'][0][1]
                self._current_line += f' "{escape_links_titles(title)}"'
            self._current_line += ')'

    def text(self, block, text):
        if self._inside_codespan:
            width = self._get_currently_applied_width()
            indent = self._get_currently_applied_indent()

            if len(self._current_line) + len(text) + 1 > width:
                self._current_line = self._current_line.rstrip('`').rstrip(' ')
                self.output += f'{indent}{self._current_line}\n'
                self._current_line = '`'

            n_backticks = min_not_max_chars_in_a_row(
                self.code_start_string[0],
                text,
            ) - 1
            if n_backticks:
                self._current_line += n_backticks * '`'

            self._current_line += f'{text}{n_backticks * "`"}'
        elif self._current_wikilink_target:
            if text != self._current_wikilink_target:
                self._current_line += (
                    f'{self._current_wikilink_target}|{text}'
                )
            else:
                self._current_line += text
            return
        else:
            if self._current_aspan_href:
                if (
                    self._current_aspan_href == text
                    and not self._current_aspan_title
                ):
                    self._current_line = (
                        f"{self._current_line.rstrip(' [')} <{text}>"
                    )
                    return

            if text == self.italic_start_string:
                text = self.italic_start_string_escaped
            elif text == self.code_start_string:
                text = self.code_start_string_escaped
            elif text == self.code_end_string:  # pragma: no cover
                text = self.code_end_string_escaped
            elif text == self.italic_end_string:  # pragma: no cover
                text = self.italic_end_string_escaped

            text_splits = text.split(' ')
            width = self._get_currently_applied_width()
            if self._current_aspan_href:  # links wrapping
                if len(self._current_line) + len(text_splits[0]) + 1 > width:
                    indent = self._get_currently_applied_indent()
                    # new link text in newline
                    self._current_line = self._current_line[:-1].rstrip(' ')
                    self.output += f'{indent}{self._current_line}\n'
                    self._current_line = '['
                width *= .95        # latest word in newline

            for i, text_split in enumerate(text_splits):
                # +1 is a space here
                if len(self._current_line) + len(text_split) + 1 > width:
                    if i or (
                        self._current_line and self._current_line[-1] == ' '
                    ):
                        indent = self._get_currently_applied_indent()
                        self.output += f'{indent}{self._current_line}\n'
                        self._current_line = ''
                        width = self._get_currently_applied_width()
                        if self._current_aspan_href:
                            width *= .95
                elif i:
                    self._current_line += ' '
                self._current_line += text_split

    def wrap(self, text):
        """Wraps reasonably Markdown lines."""
        parser = md4c.GenericParser(
            0,
            **{ext: True for ext in self.md4c_extensions},
        )
        parser.parse(
            text,
            self.enter_block,
            self.leave_block,
            self.enter_span,
            self.leave_span,
            self.text,
        )

        if self._current_line:
            self.output += (
                f'{self._get_currently_applied_indent()}{self._current_line}'
            )
        if self.first_line_width == self.width:  # is not blockquote nor list
            self.output += '\n'
        return self.output


def solve_link_reference_targets(translations):
    """Solve link reference targets in markdown blocks.

    Given a dictionary of msgid/msgstr translations, those link references
    targets will be resolved and returned in a new dictionary.

    Args:
        translations (dictionary): Mapping of msgid-msgstr entries from which
            the resolved translations will be extracted.

    Returns:
        dict: New created messages with solved link reference targets.
    """
    solutions = {}

    # dictionary with defined link references and their targets
    link_references_text_targets = []

    # compound by dictionaries with `original_msgid`, `original_msgstr` and
    # `link_reference_matchs`
    msgid_msgstrs_with_links = []

    # discover link reference definitions
    for msgid, msgstr in translations.items():
        if msgid[0] == '[':  # filter for performance improvement
            msgid_match = re.search(LINK_REFERENCE_RE, msgid)
            if msgid_match:
                msgstr_match = re.search(LINK_REFERENCE_RE, msgstr)
                if msgstr_match:
                    link_references_text_targets.append((
                        msgid_match.groups(),
                        msgstr_match.groups(),
                    ))
        msgid_matchs = re.findall(LINK_REFERENCED_LINK_RE, msgid)
        if msgid_matchs:
            msgstr_matchs = re.findall(LINK_REFERENCED_LINK_RE, msgstr)
            if msgstr_matchs:
                msgid_msgstrs_with_links.append((
                    msgid, msgstr, msgid_matchs, msgstr_matchs,
                ))

    # original msgid, original msgstr,
    # msgid link reference matchs, msgstr link reference matchs
    for (
            orig_msgid, orig_msgstr, msgid_linkr_groups, msgstr_linkr_groups,
    ) in msgid_msgstrs_with_links:
        # search if msgid and link reference matchs are inside
        # `link_references_text_targets`
        #
        # if so, replace in original messages link referenced targets with
        # real targets and store them in solutions
        new_msgid, new_msgstr = (None, None)

        for msgid_linkr_group in msgid_linkr_groups:
            for link_reference_text_targets in link_references_text_targets:

                # link_reference_text_targets[msgid][link_reference]
                if link_reference_text_targets[0][0] == msgid_linkr_group[1]:
                    replacer = (
                        f'[{msgid_linkr_group[0]}][{msgid_linkr_group[1]}]'
                    )
                    replacement = (
                        # link_reference_text_targets[msgid][target]
                        f'[{msgid_linkr_group[0]}]'
                        f'({link_reference_text_targets[0][1]})'
                    )

                    if new_msgid is None:
                        # first referenced link replacement in msgid
                        new_msgid = orig_msgid.replace(replacer, replacement)
                    else:
                        # consecutive referenced link replacements in msgid
                        new_msgid = new_msgid.replace(replacer, replacement)
                    break

        # the same game as above, but now for msgstrs

        for msgstr_linkr_group in msgstr_linkr_groups:
            for link_reference_text_targets in link_references_text_targets:

                # link_reference_text_targets[msgstr][link_reference]
                if link_reference_text_targets[1][0] == msgstr_linkr_group[1]:
                    replacer = (
                        f'[{msgstr_linkr_group[0]}][{msgstr_linkr_group[1]}]'
                    )
                    replacement = (
                        # link_reference_text_targets[msgstr][target]
                        f'[{msgstr_linkr_group[0]}]'
                        f'({link_reference_text_targets[1][1]})'
                    )

                    if new_msgstr is None:
                        # first referenced link replacement in msgid
                        new_msgstr = orig_msgstr.replace(replacer, replacement)
                    else:
                        # consecutive referenced link replacements in msgid
                        new_msgstr = new_msgstr.replace(replacer, replacement)
                    break

        # store in solutions
        solutions[new_msgid] = new_msgstr

        # print("----> new_msgid", new_msgid)
        # print("----> new_msgstr", new_msgstr)

    # print("----> link_references_text_targets", link_references_text_targets)
    # print("----> msgid_msgstrs_with_links", msgid_msgstrs_with_links)
    # print("----> solutions", solutions)
    return solutions
