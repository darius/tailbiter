"""
Original by Kragen Sitaker. Refactored and hacked to:
- look for code in ```quoted blocks``` instead of indented blocks
- support versions like handaxeweb.lua
- also support versions of the form "v2+"
- write to subdirectories
"""

import re, sys

new_chunk_pattern = re.compile(r'# in (.*?):\s*$')
chunk_ref_pattern = re.compile(r'(?m)^([ \t]*)<<(.*)>>[ \t]*\n')

def main(argv, infile):
    chunks = parse(infile)
    if argv[1:] == ['--list']:
        for name in sorted(find_roots(chunks)):
            print name
    else:
        if not argv[1:]:
            sys.stdout.write(expand(chunks, '*'))
        else:
            name, version = (argv[1], '0') if len(argv) == 2 else argv[1:]
            v = int(version)
            filename = '%d/%s' % (v, name)
            with open(filename, 'w') as outfile:
                outfile.write(expand(chunks, name, v))

def parse(infile):
    "Make a chunks table from :infile."
    chunk_name, chunks = '*', {}
    lines = iter(infile)
    for line in lines:
        if line.startswith("```"):
            line = next(lines)
            new_chunk = new_chunk_pattern.match(line)
            if new_chunk:
                chunk_name = new_chunk.group(1)
                line = next(lines)
            while line.rstrip() != "```":
                chunks[chunk_name] = chunks.get(chunk_name, '') + line
                line = next(lines)
    return chunks

def find_roots(chunks):
    "Return a set of the chunk_names that aren't referenced in chunks."
    chunk_refs = {name
                  for s in chunks.values()
                  for indent, name in chunk_ref_pattern.findall(s)}
    return set(chunks.keys()) - chunk_refs

def expand(chunks, name, version):
    "Return the named chunk with any chunk-references recursively expanded."
    template, latest = '', -1
    for v in range(version+1):
        t = chunks.get(name + ' v%d+' % v, '')
        if t:
            latest = v
            template += t
    for v in range(version, latest, -1):
        t = chunks.get(name + ' v%d' % v, '')
        if t:
            template += t
            break
    if not template:
        template = chunks[name]
    return chunk_ref_pattern.sub(
        lambda mo: indent(mo.group(1), expand(chunks, mo.group(2), version)),
        template)

def indent(dent, text):
    "Return :text with :dent prepended to every line."
    return re.sub(r'(?m)^(?=.)', dent, text) # (?=.) to exclude \Z

if __name__ == '__main__':
    main(sys.argv, sys.stdin)
