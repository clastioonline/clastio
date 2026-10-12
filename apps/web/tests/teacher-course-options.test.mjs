import assert from 'node:assert/strict';
import { test } from 'node:test';
import { normalizeTeacherCourseSelection, synchronizeOnboardingTeachingClasses, teacherCourseOptions, teacherCourseSelectionValid, teacherEducationStage, teacherEducationStages } from '../lib/teacher-course-options.ts';

const savedClasses = [
  { id: 'physics-10', name: '10A', grade: '10', subject: 'Physics', curriculum: 'british' },
  { id: 'biology-11', name: '11B', grade: '11', subject: 'Biology', curriculum: 'british' },
  { id: 'science-8', name: '8C', grade: '8', subject: 'Science', curriculum: 'cbse' },
];

test('onboarding choices exclude unrelated grades, subjects and classes', () => {
  const options = teacherCourseOptions({ subjects: ['Physics', ' Biology ', 'physics'], grades: ['10', '11'] }, savedClasses);
  assert.deepEqual(options.subjects, ['Physics', 'Biology']);
  assert.deepEqual(options.grades, ['10', '11']);
  assert.deepEqual(options.classes.map(item => item.id), ['physics-10', 'biology-11']);
  assert.equal(teacherCourseSelectionValid({ grade: '8', subject: 'Science', class_section_id: '' }, options), false);
});

test('saved classes provide teaching choices for older profiles without onboarding lists', () => {
  const options = teacherCourseOptions({}, savedClasses);
  assert.deepEqual(options.subjects, ['Physics', 'Biology', 'Science']);
  assert.deepEqual(options.grades, ['10', '11', '8']);
  assert.deepEqual(teacherCourseOptions({}, []), { subjects: [], grades: [], classes: [] });
});

test('a supplied class determines the teaching pair and stale brief values are corrected', () => {
  const options = teacherCourseOptions({ subjects: ['Physics', 'Biology'], grades: ['10', '11'] }, savedClasses);
  assert.deepEqual(normalizeTeacherCourseSelection({ grade: '8', subject: 'Science', class_section_id: 'biology-11' }, options), {
    grade: '11', subject: 'Biology', class_section_id: 'biology-11',
  });
  assert.deepEqual(normalizeTeacherCourseSelection({ grade: '8', subject: 'Science', class_section_id: 'science-8' }, options), {
    grade: '10', subject: 'Physics', class_section_id: '',
  });
});

test('class mismatches cannot be submitted and profile spelling is used consistently', () => {
  const options = teacherCourseOptions({ subjects: ['physics'], grades: [' 10 '] }, savedClasses);
  assert.deepEqual(normalizeTeacherCourseSelection({ grade: '10', subject: 'Physics', class_section_id: 'physics-10' }, options), {
    grade: '10', subject: 'physics', class_section_id: 'physics-10',
  });
  assert.equal(teacherCourseSelectionValid({ grade: '11', subject: 'physics', class_section_id: 'physics-10' }, options), false);
  assert.equal(teacherCourseSelectionValid({ grade: '10', subject: 'physics', class_section_id: 'unknown' }, options), false);
  assert.equal(teacherCourseSelectionValid({ grade: '10', subject: 'physics', class_section_id: 'physics-10' }, options), true);
});

test('changing onboarding choices updates pending classes without losing entered names', () => {
  const pending = [{ name: 'Blue group', grade: '8', subject: 'Science' }, { name: '', grade: '11', subject: 'Biology' }];
  const synchronized = synchronizeOnboardingTeachingClasses(pending, { subjects: ['Physics', 'Biology'], grades: ['10', '11'] });
  assert.deepEqual(synchronized, [{ name: 'Blue group', grade: '10', subject: 'Physics' }, pending[1]]);
  assert.equal(synchronized[1], pending[1]);
  assert.deepEqual(synchronizeOnboardingTeachingClasses(pending, { subjects: [], grades: [] }), [
    { name: 'Blue group', grade: '', subject: '' }, { name: '', grade: '', subject: '' },
  ]);
});

test('generation stages follow the selected profile or the teacher’s actual grades', () => {
  assert.deepEqual(teacherEducationStages({}, ['KG', '6', 'Year 10', 'Undergraduate year 1']), ['early_years', 'primary', 'secondary', 'university']);
  assert.deepEqual(teacherEducationStages({ education_stages: ['secondary', 'unknown', 'secondary'] }, ['6']), ['secondary']);
  assert.equal(teacherEducationStage('Grade 8'), 'secondary');
  assert.equal(teacherEducationStage('FS2'), 'early_years');
  assert.equal(teacherEducationStage('Unknown'), undefined);
});
