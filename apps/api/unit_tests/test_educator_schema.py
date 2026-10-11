"""Backward-design, demo timeline, provenance and additive-schema contracts."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint
from test_content_quality import deck

from app.ai.schema_utils import strict_schema
from app.api.routes import teacher
from app.generation.educator_specs import DemoClassContent, GeneratedResourceContent, UAEPlanContent
from app.models import DemoClass, DigitalResource, LessonPlan, TeacherProfile


def plan_dict():
    connection = {'relevant':True,'connection_or_reason':'UAE mangroves support local coastal biodiversity.',
                  'classroom_application':'Compare a mangrove habitat with a school garden.'}
    strategy = {'learning_barrier':'Reading a dense paragraph','scaffold':'Use labelled pictures and short chunks.',
                'assessment_accommodation':'Allow a spoken response or annotated diagram.'}
    return {'schema_version':1,'title':'Mangrove ecosystems','topic':'Ecosystems','subject':'Science','grade':'6',
        'curriculum':'british','language':'en','education_stage':'secondary','framework':'khda','duration_minutes':15,
        'learning_objectives':[{'id':'o1','description':'Explain a relationship in a mangrove food chain.',
            'observable_action':'explain','success_measure':'Name two organisms and correctly explain energy transfer.',
            'bloom_level':'understand'}],
        'success_criteria':[{'id':'c1','objective_ids':['o1'],'description':'Explain one transfer of energy.',
            'observable_evidence':'A correctly labelled two-organism food chain with an explanation.'}],
        'cross_curricular_links':[{'subject':'Geography','activity':'Locate a UAE mangrove coast.',
            'evidence_of_learning':'Explain why coastal conditions affect this habitat.'}],
        'uae_context':{'national_identity':connection,'moral_education':connection,'arabic_culture':connection},
        'differentiation':{'sen':[strategy],'ell':[strategy],'core':'Explain a two-organism food chain.',
                           'extension':'Predict a consequence of changing one population.'},
        'formative_assessment':[{'id':'a1','objective_ids':['o1'],'tool':'Mini whiteboards',
            'question_or_task':'Draw and explain a two-organism food chain.','expected_response':'The arrow shows energy transfer from a producer to a consumer.',
            'evidence_to_record':'Accurate arrow direction and an explanation.','teaching_response':'Re-model arrow direction if it is reversed.'}],
        'lesson_sequence':[{'name':'Hook, explanation and practice','duration_minutes':15,'objective_ids':['o1'],
            'teacher_actions':'Model a food chain, then question students.','student_actions':'Explain their own food chain.',
            'assessment_ids':['a1']}],
        'prerequisites':['Know what an organism is.'],'homework':'Find another local habitat example.',
        'resources':['Habitat photographs'],'source_references':[],
        'review_checks':{'alignment_status':'teacher_review_required','framework_references':[],
                         'evidence_gaps':['Verify the school-prescribed textbook.'],
                         'teacher_checks':['Check the activity against class support plans.']}}


def test_complete_plan_has_structured_backward_design_and_inclusion():
    plan = UAEPlanContent.model_validate(plan_dict())
    assert plan.learning_objectives[0].id == plan.formative_assessment[0].objective_ids[0]
    assert plan.differentiation.sen[0].scaffold
    assert plan.uae_context.arabic_culture.classroom_application
    assert plan.review_checks.alignment_status == 'teacher_review_required'


@pytest.mark.parametrize('field',['learning_objectives','success_criteria','cross_curricular_links','uae_context',
                                 'differentiation','formative_assessment','lesson_sequence'])
def test_required_regulatory_planning_fields_cannot_be_omitted(field):
    payload = plan_dict()
    del payload[field]
    with pytest.raises(ValidationError):
        UAEPlanContent.model_validate(payload)


@pytest.mark.parametrize('change',['unknown_objective','uncovered_objective','unknown_assessment','timing',
                                  'nonmeasurable','empty_scaffold','fake_approval','university_school_claim'])
def test_invalid_planning_alignment_is_rejected(change):
    payload = plan_dict()
    if change == 'unknown_objective':
        payload['formative_assessment'][0]['objective_ids']=['invented']
    elif change == 'uncovered_objective':
        payload['learning_objectives'].append({**payload['learning_objectives'][0],'id':'o2'})
    elif change == 'unknown_assessment':
        payload['lesson_sequence'][0]['assessment_ids']=['invented']
    elif change == 'timing':
        payload['lesson_sequence'][0]['duration_minutes']=10
    elif change == 'nonmeasurable':
        payload['learning_objectives'][0]['observable_action']='know'
    elif change == 'empty_scaffold':
        payload['differentiation']['sen'][0]['scaffold']=' '
    elif change == 'fake_approval':
        payload['review_checks']['alignment_status']='KHDA-approved'
    elif change == 'university_school_claim':
        payload['education_stage']='university'
    with pytest.raises(ValidationError):
        UAEPlanContent.model_validate(payload)


def demo_dict():
    ppt = deck()
    for slide in ppt.slides:
        slide.timing_minutes=15/len(ppt.slides)
    ppt.lesson_plan.title=plan_dict()["title"]
    ppt.lesson_plan.duration_minutes=15
    ppt.lesson_plan.objectives=[item["description"] for item in plan_dict()["learning_objectives"]]
    ppt.lesson_plan.success_criteria=[item["description"] for item in plan_dict()["success_criteria"]]
    for index in range(3):
        group=ppt.slides[len(ppt.slides)*index//3:len(ppt.slides)*(index+1)//3]
        for slide in group:
            slide.timing_minutes=5/len(group)
    ppt.lesson_plan.phases[0].minutes=15
    for phase in ppt.lesson_plan.phases[1:]:
        phase.minutes=0
    return {'lesson_plan':plan_dict(),'hook':{'teacher_says':'Which habitat protects our coast?',
        'learner_interaction':'Compare two habitat photographs.','materials':['Photographs']},
        'teacher_script':[{'order':index+1,'start_seconds':index*300,'end_seconds':(index+1)*300,
            'slide_numbers':[slide.number for slide in ppt.slides[len(ppt.slides)*index//3:len(ppt.slides)*(index+1)//3]],'teacher_says':'Explain the food chain.',
            'teacher_does':'Model the arrow direction.','expected_student_response':'Energy moves to the consumer.',
            'formative_check':'Check the explanation.','transition':'Share the exit ticket.'} for index in range(3)],
        'slide_payload':ppt.model_dump()}


def test_demo_script_and_slides_share_an_exact_fifteen_minute_timeline():
    demo=DemoClassContent.model_validate(demo_dict())
    assert demo.teacher_script[-1].end_seconds == 900
    assert sum(slide.timing_minutes for slide in demo.slide_payload.slides) == pytest.approx(15)


@pytest.mark.parametrize('change',['gap','missing_slide','uncovered_slide','slide_timing','short_demo','mismatched_title','missing_objective'])
def test_demo_timeline_mismatches_are_rejected(change):
    payload=demo_dict()
    if change=='gap':
        payload['teacher_script'][0]['start_seconds']=10
    elif change=='missing_slide':
        payload['teacher_script'][0]['slide_numbers']=[999]
    elif change=='uncovered_slide':
        payload['teacher_script'][0]['slide_numbers']=[1]
        payload['teacher_script'][1]['slide_numbers']=[1]
        payload['teacher_script'][2]['slide_numbers']=[1]
    elif change=='slide_timing':
        payload['slide_payload']['slides'][0]['timing_minutes']=10
    elif change=='mismatched_title':
        payload['slide_payload']['lesson_plan']['title']='Unrelated lesson'
    elif change=='missing_objective':
        payload['slide_payload']['lesson_plan']['objectives']=[]
    else:
        payload['lesson_plan']['duration_minutes']=10
        payload['lesson_plan']['lesson_sequence'][0]['duration_minutes']=10
    with pytest.raises(ValidationError):
        DemoClassContent.model_validate(payload)


def resource_dict():
    return {'schema_version':1,'title':'Ecosystem study guide','topic':'Ecosystems','subject':'Science',
        'education_stage':'secondary','grade':'6','curriculum':'british','language':'en','kind':'study_guide',
        'origin':'generated','overview':'Explore food chains and local habitats.',
        'chapters':[{'number':1,'title':'Food chains','learning_goals':['Explain energy transfer.'],
            'explanation':'Producers support the food chain.','definitions':['Producer: an organism that makes its food.'],
            'worked_examples':['A producer transfers energy to a consumer.'],'uae_case_study':'Illustrative mangrove habitat example.',
            'summary':'Energy transfers along a food chain.','practice_questions':['What does the arrow mean?'],
            'expected_answers':['Direction of energy transfer.'],'source_references':[]}],
        'source_references':[],'review_checks':plan_dict()['review_checks']}


def test_generated_resource_is_an_identified_primer_or_guide_not_a_publisher_book():
    payload=resource_dict()
    assert GeneratedResourceContent.model_validate(payload).origin=='generated'
    payload['kind']='book'
    with pytest.raises(ValidationError):
        GeneratedResourceContent.model_validate(payload)


def test_university_resource_can_omit_school_grade():
    payload=resource_dict()
    payload['education_stage']='university'
    payload['grade']=None
    assert GeneratedResourceContent.model_validate(payload).grade is None
    payload['education_stage']='primary'
    with pytest.raises(ValidationError):
        GeneratedResourceContent.model_validate(payload)


def test_guide_questions_cannot_lose_answers_and_chapter_order():
    payload=resource_dict()
    payload['chapters'][0]['expected_answers'].append('An extra answer')
    with pytest.raises(ValidationError):
        GeneratedResourceContent.model_validate(payload)
    payload=resource_dict()
    payload['chapters'][0]['number']=2
    with pytest.raises(ValidationError):
        GeneratedResourceContent.model_validate(payload)


def test_models_are_additive_owner_scoped_and_cache_is_private():
    assert {model.__tablename__ for model in [LessonPlan,DemoClass,DigitalResource]}=={'lesson_plans','demo_classes','digital_resources'}
    for model in [LessonPlan,DemoClass,DigitalResource]:
        assert not model.__table__.c.owner_id.nullable
    constraint=next(item for item in DigitalResource.__table__.constraints if item.name=='uq_digital_resources_owner_cache')
    assert list(constraint.columns.keys())==['owner_id','cache_key']
    assert 'regulatory_authority' in TeacherProfile.__table__.c
    assert any('ready_content' in item.name for item in LessonPlan.__table__.constraints if isinstance(item,CheckConstraint))


def test_ai_schema_forbids_unrequested_fields():
    for model in [UAEPlanContent,DemoClassContent,GeneratedResourceContent]:
        schema=strict_schema(model)
        assert schema['additionalProperties'] is False
        assert set(schema['properties'])==set(schema['required'])


async def test_existing_profile_endpoint_exposes_new_planning_defaults(monkeypatch):
    profile=SimpleNamespace(country='AE',region='Dubai',school_name='School',curriculum='british',
        subjects=['Science'],grades=['6'],teaching_languages=['en'],class_duration_minutes=45,classes_per_day=5,
        working_days=[0,1,2,3,4],teaching_style=None,onboarding_completed=True,default_template_id=None,
        metadata_policy={},regulatory_authority='not_specified',education_stages=[],planning_preferences={})
    user=SimpleNamespace(id='teacher',name='Teacher',email='teacher@example.com',locale='en',timezone='Asia/Dubai')
    monkeypatch.setattr(teacher,'_profile',AsyncMock(return_value=profile))
    db=AsyncMock()
    payload=teacher.ProfileIn(regulatory_authority='khda',education_stages=['primary'],
        planning_preferences={'ell_scaffolds':['Use sentence frames.']})
    result=await teacher.update_profile(payload,user,db)
    assert result['regulatory_authority']=='khda'
    assert result['planning_preferences']['ell_scaffolds']==['Use sentence frames.']
    assert isinstance(profile.planning_preferences,dict)


def test_assessments_cannot_be_swapped_between_unrelated_objective_phases():
    payload=plan_dict()
    payload['learning_objectives'].append({**payload['learning_objectives'][0],'id':'o2'})
    payload['success_criteria'].append({**payload['success_criteria'][0],'id':'c2','objective_ids':['o2']})
    payload['formative_assessment'].append({**payload['formative_assessment'][0],'id':'a2','objective_ids':['o2']})
    original=payload['lesson_sequence'][0]
    payload['lesson_sequence']=[{**original,'duration_minutes':7,'objective_ids':['o1'],'assessment_ids':['a2']},
                                {**original,'duration_minutes':8,'objective_ids':['o2'],'assessment_ids':['a1']}]
    with pytest.raises(ValidationError,match='phase assessment'):
        UAEPlanContent.model_validate(payload)


@pytest.mark.parametrize('field,limit',[('title',300),('topic',300),('subject',80),('grade',30),('curriculum',40),('language',10)])
def test_plan_metadata_cannot_exceed_database_column_bounds(field,limit):
    payload=plan_dict()
    payload[field]='a'*(limit+1)
    with pytest.raises(ValidationError):
        UAEPlanContent.model_validate(payload)


def test_demo_cannot_replace_the_approved_success_criteria():
    payload=demo_dict()
    payload['slide_payload']['lesson_plan']['success_criteria']=['An unrelated criterion.']
    with pytest.raises(ValidationError,match='success criteria'):
        DemoClassContent.model_validate(payload)


def test_demo_timing_cannot_drift_between_the_script_and_ppt_groups():
    payload=demo_dict()
    payload['slide_payload']['slides'][0]['timing_minutes']+=1
    payload['slide_payload']['slides'][1]['timing_minutes']-=1
    with pytest.raises(ValidationError,match='teacher-script'):
        DemoClassContent.model_validate(payload)


@pytest.mark.parametrize('value',['not-a-source','http://publisher.example/book','https://secret:password@publisher.example/book'])
def test_source_reference_needs_a_safe_url_or_file_identifier(value):
    from app.generation.educator_specs import SourceReference
    with pytest.raises(ValidationError):
        SourceReference(title='Source',url_or_file_id=value,page_or_section='1',relevance='Topic evidence')
