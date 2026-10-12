"""Reviewed publisher metadata and links, never a mirror of textbook content.

UAE and British collections come first. Supplementary references retain their
original curriculum and licence; free reading never implies permission for AI use.
Reviewed against the linked publishers on 2026-10-12.
"""
from copy import deepcopy

REVIEWED_ON = '2026-10-12'
CAMBRIDGE = 'https://www.cambridgeinternational.org/programmes-and-qualifications/'

COLLECTIONS = [
    {'id': 'moe-minhaji', 'title': 'UAE MoE textbooks — Minhaji', 'curriculum': 'moe',
     'publisher': 'UAE Ministry of Education', 'education_stages': ['primary', 'secondary'],
     'source_url': 'https://minhaji.moe.gov.ae/', 'access': 'school_login',
     'note': 'Open your official school textbook library with your school account. Confirm the subject, grade, term and edition before saving an authorised copy.'},
    {'id': 'british-cambridge-resources', 'title': 'Cambridge endorsed textbook directory', 'curriculum': 'british',
     'publisher': 'Cambridge International Education', 'education_stages': ['primary', 'secondary'],
     'source_url': 'https://www.cambridgeinternational.org/resource-centre/', 'access': 'publisher',
     'note': 'Choose your Cambridge programme and syllabus to see endorsed books, publisher access and teacher resources.'},
    {'id': 'british-cambridge-primary', 'title': 'Cambridge Primary', 'curriculum': 'british',
     'publisher': 'Cambridge International Education', 'education_stages': ['primary'],
     'source_url': CAMBRIDGE + 'cambridge-primary/', 'access': 'publisher',
     'note': 'Browse subjects and resources for the Primary programme. School or publisher access may be required.'},
    {'id': 'british-cambridge-lower-secondary', 'title': 'Cambridge Lower Secondary', 'curriculum': 'british',
     'publisher': 'Cambridge International Education', 'education_stages': ['secondary'],
     'source_url': CAMBRIDGE + 'cambridge-lower-secondary/', 'access': 'publisher',
     'note': 'Browse Lower Secondary subjects and teaching resources. Use the school-prescribed edition.'},
    {'id': 'british-pearson-igcse', 'title': 'Pearson Edexcel International GCSE', 'curriculum': 'british',
     'publisher': 'Pearson', 'education_stages': ['secondary'],
     'source_url': 'https://qualifications.pearson.com/en/qualifications/edexcel-international-gcses.html', 'access': 'publisher',
     'note': 'Choose the Edexcel subject and qualification to find specifications, support and publisher resources.'},
    {'id': 'british-cambridge-a-level', 'title': 'Cambridge International AS & A Level', 'curriculum': 'british',
     'publisher': 'Cambridge International Education', 'education_stages': ['secondary'],
     'source_url': CAMBRIDGE + 'cambridge-advanced/cambridge-international-as-and-a-levels/', 'access': 'publisher',
     'note': 'Browse subjects and endorsed resources for AS & A Level. Check your examination year.'},
    {'id': 'american-openstax', 'title': 'OpenStax high-school textbook library', 'curriculum': 'american',
     'publisher': 'OpenStax / Rice University', 'education_stages': ['secondary', 'university'],
     'source_url': 'https://openstax.org/k12', 'access': 'read_online',
     'note': 'Free reading on the publisher website. OpenStax requires written permission before use in AI offerings; these links do not import content.'},
    {'id': 'ib-publishing', 'title': 'IB classroom resources and publishing partners', 'curriculum': 'ib',
     'publisher': 'International Baccalaureate', 'education_stages': ['primary', 'secondary'],
     'source_url': 'https://ibo.org/become-an-ib-school/ib-publishing/co-publishing/', 'access': 'publisher',
     'note': 'Official co-publishing partners and programme resources. Access follows the publisher or school licence.'},
    {'id': 'cbse-ncert', 'title': 'NCERT textbooks — Classes I–XII', 'curriculum': 'cbse',
     'publisher': 'NCERT', 'education_stages': ['primary', 'secondary'],
     'source_url': 'https://ncert.nic.in/textbook.php', 'access': 'official_library',
     'note': 'Choose the class, subject and book in the official NCERT library. These are CBSE resources; they are not UAE MoE or British textbooks.'},
    {'id': 'other-siyavula', 'title': 'Siyavula school textbook library', 'curriculum': 'other',
     'publisher': 'Siyavula', 'education_stages': ['primary', 'secondary'],
     'source_url': 'https://www.siyavula.com/read', 'access': 'read_online',
     'note': 'South African CAPS books. Online text, branded PDFs and unbranded files have different licences; check the selected version.'},
]


def _cambridge(subject, code, title, edition):
    source_url = CAMBRIDGE + f'cambridge-igcse-{subject.lower()}-{code}/published-resources/'
    return {'id': f'cambridge-igcse-{code}', 'title': title, 'publisher': 'Cambridge University Press',
            'subjects': [subject], 'curriculum': 'british', 'education_stages': ['secondary'], 'grades': [],
            'language': 'en', 'edition': edition, 'source_url': source_url, 'access': 'publisher',
            'license': 'Publisher copyright — access licence required', 'license_url': source_url,
            'rights_note': 'Read the official book listing and obtain access through your school or publisher. Import or sharing needs permission.',
            'curriculum_note': f'Listed in the official Cambridge IGCSE {subject} ({code}) resource directory. Check the current syllabus and examination year.'}


def _openstax(slug, title, subject, page='1-introduction'):
    return {'id': f'openstax-{slug}', 'title': title, 'publisher': 'OpenStax / Rice University',
            'subjects': [subject], 'curriculum': 'american', 'education_stages': ['secondary', 'university'],
            'grades': [], 'language': 'en', 'edition': title.rsplit(' ', 1)[-1] if title.endswith(('2e', '3e')) else '',
            'source_url': f'https://openstax.org/books/{slug}/pages/{page}', 'access': 'read_online',
            'license': 'CC BY-NC-SA 4.0; AI use requires written permission',
            'license_url': f'https://openstax.org/books/{slug}/pages/{page}',
            'rights_note': 'Free reading on OpenStax. Written publisher permission is required before importing this content into AI offerings or using it commercially.',
            'curriculum_note': 'Supplementary reference; school year and local syllabus alignment have not been verified.'}


def _siyavula(slug, title, subjects, grade):
    return {'id': f'siyavula-{slug}-{grade}', 'title': f'{title} — Grade {grade}', 'publisher': 'Siyavula',
            'subjects': subjects, 'curriculum': 'other', 'education_stages': ['secondary'], 'grades': [str(grade)],
            'language': 'en', 'edition': '', 'source_url': f'https://www.siyavula.com/read/za/{slug}/grade-{grade}',
            'access': 'read_online', 'license': 'Online textbook text: CC BY 3.0',
            'license_url': 'https://www.siyavula.com/read#our-book-licensing',
            'rights_note': 'Attribute Siyavula when reusing online textbook text. Branded PDFs are CC BY-ND 3.0 and cannot be adapted; external videos and simulations may have different rights.',
            'curriculum_note': 'South African CAPS. Use as a supplementary reference for other curricula after checking coverage.'}


REFERENCE_BOOKS = [
    _cambridge('Physics', '0625', 'Cambridge IGCSE Physics Coursebook with Digital Access (2 Years) Third Edition', 'Third edition, 2021'),
    _cambridge('Mathematics', '0580', 'Cambridge IGCSE Mathematics Core and Extended Third Edition', 'Third edition, 2023'),
    _cambridge('Chemistry', '0620', 'Chemistry for Cambridge IGCSE Coursebook with Digital Access (2 Years) Fifth Edition', 'Fifth edition, 2021'),
    _cambridge('Biology', '0610', 'Cambridge IGCSE Biology Coursebook with Digital Access (2 Years) Fourth Edition', 'Fourth edition, 2021'),
    _openstax('physics', 'Physics', 'Physics'),
    _openstax('biology-2e', 'Biology 2e', 'Biology'),
    _openstax('concepts-biology', 'Concepts of Biology', 'Biology'),
    _openstax('biology-ap-courses', 'Biology for AP® Courses', 'Biology'),
    _openstax('chemistry-2e', 'Chemistry 2e', 'Chemistry'),
    _openstax('elementary-algebra-2e', 'Elementary Algebra 2e', 'Mathematics'),
    _openstax('intermediate-algebra-2e', 'Intermediate Algebra 2e', 'Mathematics'),
    _openstax('algebra-and-trigonometry-2e', 'Algebra and Trigonometry 2e', 'Mathematics', '1-introduction-to-prerequisites'),
    _openstax('precalculus-2e', 'Precalculus 2e', 'Mathematics', '1-introduction-to-functions'),
    _openstax('introductory-statistics-2e', 'Introductory Statistics 2e', 'Mathematics'),
    _openstax('principles-economics-3e', 'Principles of Economics 3e', 'Economics'),
    _openstax('us-history', 'U.S. History', 'History'),
    _openstax('writing-guide', 'Writing Guide with Handbook', 'English'),
    *[_siyavula('mathematics', 'Mathematics', ['Mathematics'], grade) for grade in range(7, 13)],
    *[_siyavula('natural-sciences', 'Natural Sciences', ['Science'], grade) for grade in range(7, 10)],
    *[_siyavula('physical-sciences', 'Physical Sciences', ['Science', 'Physics', 'Chemistry'], grade) for grade in range(10, 13)],
    _siyavula('life-sciences', 'Life Sciences', ['Biology', 'Science'], 10),
    _siyavula('mathematical-literacy', 'Mathematical Literacy', ['Mathematics'], 10),
]


def textbook_sources():
    """Fresh metadata only; browsing never downloads, indexes or calls AI."""
    return {'collections': [{**deepcopy(item), 'reviewed_on': REVIEWED_ON} for item in COLLECTIONS],
            'reference_books': [{**deepcopy(item), 'reviewed_on': REVIEWED_ON} for item in REFERENCE_BOOKS]}
