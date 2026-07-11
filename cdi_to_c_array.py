#!/usr/bin/env python3
"""Convert a CDI/FDI XML file into the C byte-array text block that
cdi_fdi_wizard.html's "Array" tab produces, without needing a browser.

Mirrors cdi_editor/cdi_view.html's _xmlToByteRows()/_renderMapArray() and
js/c_target.js's renderByteArray(), line for line.

Usage: python cdi_to_c_array.py path/to/CDI.xml [--preserve-whitespace] [--kind cdi|fdi]
"""
import sys
import argparse


def is_printable(ch: str) -> bool:
    code = ord(ch)
    return 32 <= code <= 126


def xml_to_byte_rows(xml_text: str, preserve_whitespace: bool):
    rows = []
    for line in xml_text.splitlines():
        if line.strip() == '':
            continue
        if preserve_whitespace:
            bytes_ = [ord(c) for c in line if is_printable(c)]
            bytes_.append(0x0A)
            comment = line
        else:
            trimmed = line.strip()
            bytes_ = [ord(c) for c in trimmed if is_printable(c)]
            comment = trimmed
        rows.append((bytes_, comment))
    return rows


def render_byte_array(rows, kind='cdi'):
    lower = kind.lower()
    upper = lower.upper()
    lines = []
    total = 0

    lines.append(f'// {upper} byte array.')
    lines.append(f'// Paste this into the .{lower} field of the node_parameters_t struct')
    layout = 'configuration layout' if lower == 'cdi' else 'train function descriptions'
    lines.append(f"// in openlcb_user_config.c to define the node's {layout}.")
    lines.append('//')
    lines.append('// NOTE: THIS IS FOR CONVENIENCE OF THOSE MANUALLY BUILDING THEIR OPENLCB_USER_CONFIG.C FILE.')
    lines.append('')
    lines.append(f'.{lower} = {{')

    for bytes_, comment in rows:
        line = ''
        for b in bytes_:
            line += f'0x{b:02X}, '
            total += 1
        line += f'  // {comment}'
        lines.append(line)

    lines.append('},')
    lines.append('')
    lines.append(f'#define USER_{upper}_ARRAY_SIZE  {total}  // Total bytes including null terminator')

    return '\n'.join(lines), total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xml_path')
    ap.add_argument('--preserve-whitespace', action='store_true')
    ap.add_argument('--kind', default='cdi', choices=['cdi', 'fdi'])
    ap.add_argument('-o', '--output', help='write to this file instead of stdout')
    args = ap.parse_args()

    with open(args.xml_path, 'r', encoding='utf-8') as f:
        xml_text = f.read().strip()

    rows = xml_to_byte_rows(xml_text, args.preserve_whitespace)
    rows.append(([0x00], 'String terminating null'))

    text, total = render_byte_array(rows, args.kind)

    if args.output:
        with open(args.output, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        print(f'Wrote {total} bytes to {args.output}', file=sys.stderr)
    else:
        print(text)


if __name__ == '__main__':
    main()
