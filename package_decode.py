import struct
from dns_structs import DNSPackage, Question, Answer
from common import types

def decode_package(bts):
    pkg = DNSPackage()
    pkg.id = unpack_short(bts[:2])
    pkg.qr, pkg.opcode, pkg.auth, pkg.trunc, pkg.rd, pkg.ra, pkg.rcode = \
        decode_flags(unpack_short(bts[2:4]))
    pkg.qdcount = unpack_short(bts[4:6])
    pkg.ancount = unpack_short(bts[6:8])
    pkg.nscount = unpack_short(bts[8:10])
    pkg.arcount = unpack_short(bts[10:12])

    offset, pkg.questions = decode_questions(bts, 12, pkg.qdcount)
    offset, pkg.answers = decode_answers(bts, offset, pkg.ancount)
    offset, pkg.authorities = decode_answers(bts, offset, pkg.nscount)
    offset, pkg.additions = decode_answers(bts, offset, pkg.arcount)
    return pkg


def decode_flags(bts):
    print(bts)
    return (
        (bts >> 15) & 0b1, 
        (bts >> 11) & 0b1111,
        (bts >> 10) & 0b1,
        (bts >> 9) & 0b1,
        (bts >> 8) & 0b1,
        (bts >> 7) & 0b1,
        bts & 0b1111)


def decode_questions(bts, offset, qdcount):
    # bts starts with questions
    questions = [] 
    for i in range(qdcount):
        offset, name = decode_name(bts, offset)
        tp = unpack_short(bts[offset:offset + 2])
        cl = unpack_short(bts[offset + 2:offset + 4])
        offset += 4
        questions.append(Question(name, tp, cl))

    return offset, questions


def decode_answers(bts, offset, count):
    answers = []
    for i in range(count):
        offset, answer = _decode_answer(bts, offset)
        answers.append(answer)
    return offset, answers


def _decode_answer(bts, offset):
    offset, name = decode_name(bts, offset)
    name = name.lower()
    tp = unpack_short(bts[offset:offset + 2])
    cl = unpack_short(bts[offset + 2:offset + 4])
    ttl = struct.unpack('!I', bts[offset + 4:offset + 8])[0]
    rdlen = unpack_short(bts[offset + 8:offset + 10])
    offset += 10
    
    if tp ==  types['A']:
        data = _decode_a_data(bts, offset)
    elif tp == types['NS'] or tp == types['PTR']:
        data = _decode_name_data(bts, offset)
    else:
        data = bts[offset:offset + rdlen].decode('cp1251')
    offset += rdlen
    return offset, Answer(name, tp, cl, ttl, data)


def _decode_a_data(bts, offset):
    data = bts[offset:offset + 4]
    ip_parts = struct.unpack('!BBBB', data)
    return '.'.join(map(str, ip_parts))


def _decode_name_data(bts, offset):
    return decode_name(bts, offset)[1].lower()

def decode_name(bts, offset):
    labels = []
    pointer_mask = 0b11 << 6

    while bts[offset] != 0:
        label = bytearray()
        length = int(bts[offset])
        if length & pointer_mask != 0:
            reduce_mask = (1 << 16) - (0b11 << 14) - 1
            pointer = unpack_short(bts[offset:offset + 2]) & reduce_mask
            prefix = '' if len(labels) == 0 else '.'.join(labels) + '.'
            return offset + 2, prefix + decode_name(bts, pointer)[1]

        for i in range(1, length + 1):
            label.append(bts[offset + i])
        offset += length + 1
        labels.append(label.decode('ascii'))
    labels.append('') 
    return offset + 1, '.'.join(labels)


def unpack_short(bts):
    return struct.unpack('!H', bts)[0]
