import re


def str_replace_from_map(s: str, map=None, mode='any'):
    if map is None:
        return s
    for k, v in map.items():
        if mode == 'whole_words':
            s = re.sub(r'\b%s\b' % k, v, s)
        elif mode == 'any':
            s = s.replace(k, v)
        else:
            raise Exception(f'{mode=} not valid')
    return s
