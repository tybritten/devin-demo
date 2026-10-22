{% extends "base.html" %}
{% load crispy_forms_tags humanize ui_tags %}
{% block title %}{{ record }}{% endblock %}
{% block content %}
<nav aria-label="breadcrumb"><ol class="breadcrumb">
  <li class="breadcrumb-item"><a href="{% url '__app__:list' %}">__Title__</a></li>
  <li class="breadcrumb-item active" aria-current="page">{{ record }}</li>
</ol></nav>
<div class="d-flex justify-content-between align-items-start mb-4">
  <div>
    <h1 class="h3 mb-1">{{ record.title }}</h1>
    {% badge record.get_status_display %}
  </div>
  {% if can_edit %}<a href="{% url '__app__:edit' record.pk %}" class="btn btn-outline-secondary">Edit</a>{% endif %}
</div>
<div class="row g-4">
  <div class="col-lg-8">
    <div class="card shadow-sm mb-4">
      <div class="card-header">Details</div>
      <div class="card-body" style="white-space: pre-line">{{ record.description|default:"No description." }}</div>
    </div>
    <div class="card shadow-sm">
      <div class="card-header">Activity</div>
      <div class="card-body">
        {% if perms.__app__.change___model__ %}
        <form method="post" action="{% url '__app__:comment' record.pk %}" class="mb-4">
          {% csrf_token %}
          {{ comment_form|crispy }}
          <button type="submit" class="btn btn-sm btn-outline-secondary">Comment</button>
        </form>
        {% endif %}
        <ul class="timeline mb-0">
          {% for event in events %}
          <li>
            <div class="small text-body-secondary"><strong class="text-body">{{ event.actor|person:"System" }}</strong> · <span title="{{ event.created_at }}">{{ event.created_at|naturaltime }}</span></div>
            <div>
              {% if event.kind == "status_changed" %}Moved from <strong>{{ event.get_from_status_display }}</strong> to <strong>{{ event.get_to_status_display }}</strong>
              {% elif event.kind != "comment" %}{{ event.get_kind_display }}{% endif %}
            </div>
            {% if event.message %}<div class="bg-body-tertiary rounded p-2 mt-1" style="white-space: pre-line">{{ event.message }}</div>{% endif %}
          </li>
          {% endfor %}
        </ul>
      </div>
    </div>
  </div>
  <div class="col-lg-4">
    {% if transition_form %}
    <div class="card shadow-sm mb-4 border-primary">
      <div class="card-header">Next step</div>
      <div class="card-body">
        <form method="post" action="{% url '__app__:transition' record.pk %}">
          {% csrf_token %}
          {{ transition_form|crispy }}
          <button type="submit" class="btn btn-primary">Update status</button>
        </form>
      </div>
    </div>
    {% endif %}
    <div class="card shadow-sm">
      <div class="card-body">
        <dl class="row mb-0 small">
          <dt class="col-5">Owner</dt><dd class="col-7">{{ record.owner|person }}</dd>
          <dt class="col-5">Created by</dt><dd class="col-7">{{ record.created_by|person }}</dd>
          <dt class="col-5">Created</dt><dd class="col-7">{{ record.created_at|date:"M j, Y H:i" }}</dd>
          <dt class="col-5">Updated</dt><dd class="col-7">{{ record.updated_at|date:"M j, Y H:i" }}</dd>
        </dl>
      </div>
    </div>
  </div>
</div>
{% endblock %}
