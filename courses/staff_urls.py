"""Staff course builder URLs, mounted at /staff/courses/."""

from django.urls import path

from . import staff_views as v

app_name = "course_builder"

urlpatterns = [
    path("", v.course_list, name="course_list"),
    path("new/", v.course_create, name="course_create"),
    path("import/", v.sheet_import, name="sheet_import"),
    path("<int:course_id>/", v.course_detail, name="course"),
    path("<int:course_id>/publish/", v.course_publish, name="course_publish"),
    path("<int:course_id>/modules/new/", v.module_create, name="module_create"),

    path("modules/<int:module_id>/", v.module_detail, name="module"),
    path("modules/<int:module_id>/delete/", v.module_delete, name="module_delete"),
    path("modules/<int:module_id>/lessons/new/", v.lesson_create, name="lesson_create"),
    path("modules/<int:module_id>/outcomes/new/", v.outcome_create, name="outcome_create"),
    path("outcomes/<int:outcome_id>/delete/", v.outcome_delete, name="outcome_delete"),

    path("lessons/<int:lesson_id>/", v.lesson_detail, name="lesson"),
    path("lessons/<int:lesson_id>/delete/", v.lesson_delete, name="lesson_delete"),
    path("lessons/<int:lesson_id>/preview/", v.lesson_preview, name="lesson_preview"),
    path("lessons/<int:lesson_id>/steps/new/", v.step_create, name="step_create"),

    path("steps/<int:step_id>/", v.step_edit, name="step"),
    path("steps/<int:step_id>/delete/", v.step_delete, name="step_delete"),
    path("steps/<int:step_id>/questions/add/", v.step_question_add, name="step_question_add"),
    path("step-questions/<int:question_id>/", v.step_question_update, name="step_question_update"),
    path("step-questions/<int:question_id>/remove/", v.step_question_remove, name="step_question_remove"),

    path("api/reorder/<str:kind>/<int:parent_id>/", v.reorder, name="reorder"),
    path("api/search/", v.search_questions, name="search"),
]
