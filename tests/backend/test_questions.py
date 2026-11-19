"""Tests for questions endpoints (section 5 of the contract)."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def test_create_question_includes_co_number(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1 desc")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    resp = client.post("/questions", headers=h, json={
        "module_id": mod["module_id"],
        "co_id": co["co_id"],
        "stem": "What is 2+2?",
        "options": ["2", "3", "4", "5"],
        "correct_option": 2,
    })
    assert resp.status_code == 201
    q = resp.json()
    assert q["status"] == "draft"
    assert q["source"] == "faculty"
    assert q["co_number"] == 1
    assert q["options"] == ["2", "3", "4", "5"]
    assert q["correct_option"] == 2
    assert q["created_by"] == faculty["user_id"]


def test_list_questions_by_module(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1 desc")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    ctx.make_question(mod["module_id"], co["co_id"], faculty_user_id=faculty["user_id"],
                      status="draft", stem="Q draft")
    ctx.make_question(mod["module_id"], co["co_id"], faculty_user_id=faculty["user_id"],
                      status="approved", stem="Q approved")

    resp = client.get(f"/questions?module_id={mod['module_id']}", headers=h)
    assert resp.status_code == 200
    qs = resp.json()
    assert len(qs) == 2
    for q in qs:
        assert q["co_number"] == 1

    # Filter by status
    resp = client.get(f"/questions?module_id={mod['module_id']}&status=approved", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_list_questions_requires_module_id(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)

    resp = client.get("/questions", headers=h)
    assert resp.status_code == 422


def test_approve_and_reject_question(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1 desc")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")
    q = ctx.make_question(mod["module_id"], co["co_id"], faculty_user_id=faculty["user_id"])

    # Approve
    resp = client.post(f"/questions/{q['question_id']}/approve", headers=h)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    # Reject
    resp = client.post(f"/questions/{q['question_id']}/reject", headers=h)
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_batch_creates_ai_drafts(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1 desc")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    resp = client.post("/questions/batch", headers=h, json={
        "questions": [
            {
                "module_id": mod["module_id"],
                "co_id": co["co_id"],
                "stem": "Batch Q1?",
                "options": ["A", "B", "C", "D"],
                "correct_option": 0,
                "source": "AI",
            },
            {
                "module_id": mod["module_id"],
                "co_id": co["co_id"],
                "stem": "Batch Q2?",
                "options": ["A", "B", "C", "D"],
                "correct_option": 1,
                "source": "AI",
            },
        ]
    })
    assert resp.status_code == 201
    qs = resp.json()
    assert len(qs) == 2
    for q in qs:
        assert q["source"] == "AI"
        assert q["status"] == "draft"
        assert q["co_number"] == 1


def test_faculty_cannot_create_question_for_others_module(client, ctx):
    faculty_a = ctx.make_faculty()
    faculty_b = ctx.make_faculty()
    subj = ctx.make_subject(faculty_b["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1 desc")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")

    token = ctx.login(email=faculty_a["email"], password=faculty_a["password"]).json()["access_token"]
    h = ctx.headers(token)

    resp = client.post("/questions", headers=h, json={
        "module_id": mod["module_id"],
        "co_id": co["co_id"],
        "stem": "Cannot create",
        "options": ["A", "B", "C", "D"],
        "correct_option": 0,
    })
    assert resp.status_code == 404


def test_patch_question(client, ctx):
    faculty = ctx.make_faculty()
    token = ctx.login(email=faculty["email"], password=faculty["password"]).json()["access_token"]
    h = ctx.headers(token)
    subj = ctx.make_subject(faculty["user_id"])
    co = ctx.make_co(subj["subject_id"], 1, "CO1 desc")
    mod = ctx.make_module(subj["subject_id"], 1, "Module 1")
    q = ctx.make_question(mod["module_id"], co["co_id"], faculty_user_id=faculty["user_id"])

    resp = client.patch(f"/questions/{q['question_id']}", headers=h,
                        json={"stem": "Updated stem", "difficulty": "hard"})
    assert resp.status_code == 200
    assert resp.json()["stem"] == "Updated stem"
    assert resp.json()["difficulty"] == "hard"


@pytest.fixture
def review_module(ctx):
    owner = ctx.make_faculty()
    token = ctx.login(email=owner["email"], password=owner["password"]).json()["access_token"]
    subject = ctx.make_subject(owner["user_id"])
    module = ctx.make_module(subject["subject_id"], 1)
    return ctx.headers(token), owner["user_id"], module


def test_batch_preserves_only_verified_slide_citations(client, db, review_module):
    headers, _, module = review_module
    mid = module['module_id']
    quote = 'Binary search requires sorted input.'
    db.execute(text('INSERT INTO content_chunks (module_id, slide_number, text) VALUES (:mid, 7, :quote)'),
               {'mid': mid, 'quote': quote})
    db.commit()
    draft = {'module_id': mid, 'stem': 'What does binary search require?',
             'options': ['Sorted input', 'A heap', 'A tree', 'A queue'], 'correct_option': 0,
             'source_slide_number': 7, 'source_quote': quote}
    for change in ({'source_slide_number': 8}, {'source_quote': 'Invented'}, {'source_quote': None}):
        response = client.post('/questions/batch', headers=headers, json={'questions': [draft, {**draft, **change}]})
        assert response.status_code == 422
    response = client.post('/questions/batch', headers=headers, json={'questions': [draft]})
    assert response.status_code == 201
    listed = client.get('/questions', headers=headers, params={'module_id': mid}).json()
    assert len(listed) == 1  # No partial insert on an invalid batch.
    assert (listed[0]['source_slide_number'], listed[0]['source_quote'], listed[0]['status']) == (7, quote, 'draft')


def test_batch_unmapped_draft_review(client, review_module):
    headers, _, module = review_module
    draft = {"module_id": module["module_id"], "stem": "Unmapped?",
             "options": ["A", "B", "C", "D"], "correct_option": 0}
    response = client.post("/questions/batch", headers=headers, json={
        "questions": [draft, {**draft, "co_id": None, "status": "approved"}]})
    assert response.status_code == 201
    questions = response.json()
    assert len(questions) == 2
    for question in questions:
        assert question["co_id"] is None and question["co_number"] is None
        assert (question["source"], question["status"]) == ("AI", "draft")
    listed = client.get("/questions", headers=headers, params={
        "module_id": module["module_id"], "status": "draft"})
    assert {q["id"] for q in listed.json()} == {q["id"] for q in questions}
    path = f"/questions/{questions[0]['id']}"
    edited = client.patch(path, headers=headers, json={"stem": "Revised"})
    assert edited.status_code == 200 and edited.json()["stem"] == "Revised"
    rejected = client.post(path + "/reject", headers=headers)
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    assert rejected.json()["co_id"] is None


@pytest.mark.parametrize("route", ["approve", "patch"])
def test_approval_requires_mapping(client, ctx, review_module, route):
    headers, owner_id, module = review_module
    q = ctx.make_question(module["module_id"], None, faculty_user_id=owner_id)
    path = f"/questions/{q['question_id']}"
    if route == "approve":
        response = client.post(path + "/approve", headers=headers)
    else:
        response = client.patch(path, headers=headers, json={"status": "approved"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"
    co = ctx.make_co(module["subject_id"], 1)
    mapped = client.patch(path, headers=headers, json={"co_id": co["co_id"]})
    assert mapped.status_code == 200 and mapped.json()["status"] == "draft"
    assert mapped.json()["co_number"] == 1
    approved = client.post(path + "/approve", headers=headers)
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    cleared = client.patch(path, headers=headers, json={"co_id": None})
    assert cleared.status_code == 409
    draft = client.patch(path, headers=headers, json={"co_id": None, "status": "draft"})
    assert draft.status_code == 200 and draft.json()["co_id"] is None


def test_storage_rejects_unmapped_approval(ctx, db, review_module):
    _, owner_id, module = review_module
    q = ctx.make_question(module["module_id"], None, faculty_user_id=owner_id)
    with pytest.raises(IntegrityError) as error, db.begin_nested():
        db.execute(text("UPDATE questions SET status = 'approved' WHERE id = :id"),
                   {"id": q["question_id"]})
    assert getattr(error.value.orig, "sqlstate", None) == "23514"


def test_patch_question_stays_in_original_subject(client, ctx, review_module):
    headers, owner_id, module = review_module
    other_subject = ctx.make_subject(owner_id)["subject_id"]
    other_module = ctx.make_module(other_subject, 1)["module_id"]
    other_co = ctx.make_co(other_subject, 1)["co_id"]
    q = ctx.make_question(module["module_id"], None, faculty_user_id=owner_id)
    path = f"/questions/{q['question_id']}"
    for changes in ({"module_id": other_module}, {"co_id": other_co},
                    {"module_id": other_module, "co_id": other_co, "status": "approved"}):
        assert client.patch(path, headers=headers, json=changes).status_code == 404
    sibling = ctx.make_module(module["subject_id"], 2)["module_id"]
    co = ctx.make_co(module["subject_id"], 2)["co_id"]
    moved = client.patch(path, headers=headers, json={"module_id": sibling, "co_id": co,
                                                      "status": "approved"})
    assert moved.status_code == 200
    assert (moved.json()["module_id"], moved.json()["co_number"]) == (sibling, 2)


def test_cannot_approve_legacy_cross_subject_mapping(client, ctx, review_module):
    headers, owner_id, module = review_module
    other_co = ctx.make_co(ctx.make_subject(owner_id)["subject_id"], 1)
    q = ctx.make_question(module["module_id"], other_co["co_id"], faculty_user_id=owner_id)
    response = client.post(f"/questions/{q['question_id']}/approve", headers=headers)
    assert response.status_code == 404


def test_review_cannot_remap_question_from_published_quiz(client, ctx, db, review_module):
    headers, owner_id, module = review_module
    co = ctx.make_co(module["subject_id"], 1)
    q = ctx.make_question(module["module_id"], co["co_id"], owner_id, status="approved")
    quiz = ctx.make_quiz(module["module_id"], module["subject_id"], question_ids=[q["question_id"]])
    db.execute(text("UPDATE quizzes SET published = true WHERE id = :id"), {"id": quiz["quiz_id"]})
    db.commit()
    replacement = ctx.make_co(module["subject_id"], 2)
    path = f"/questions/{q['question_id']}"
    response = client.patch(path, headers=headers, json={"co_id": replacement["co_id"]})
    assert response.status_code == 409
    assert client.patch(path, headers=headers, json={}).json()["co_id"] == co["co_id"]


def test_openapi_describes_unmapped_batch_questions(client):
    spec = client.get("/openapi.json").json()

    def resolve(schema):
        if "$ref" in schema:
            return spec["components"]["schemas"][schema["$ref"].split("/")[-1]]
        return schema

    operation = spec["paths"]["/questions/batch"]["post"]
    request = resolve(operation["requestBody"]["content"]["application/json"]["schema"])
    item = resolve(request["properties"]["questions"]["items"])
    assert "co_id" not in item["required"]
    assert {"type": "null"} in item["properties"]["co_id"]["anyOf"]
    response = operation["responses"]["201"]["content"]["application/json"]["schema"]
    question = resolve(response["items"])
    for key in ("co_id", "co_number"):
        assert key in question["required"]
        assert {"type": "null"} in question["properties"][key]["anyOf"]
