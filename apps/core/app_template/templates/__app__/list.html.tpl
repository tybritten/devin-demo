{% extends "base.html" %}
{% load ui_tags %}
{% block title %}__Title__{% endblock %}
{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
  <h1 class="h3 mb-0">__Title__</h1>
  {% if perms.__app__.add___model__ %}<a href="{% url '__app__:create' %}" class="btn btn-primary">New __model_title__</a>{% endif %}
</div>
<form method="get" class="row g-2 align-items-end mb-3">
  <div class="col-md-6">
    <label class="form-label small" for="id_q">Search</label>
    <input type="search" class="form-control" name="q" id="id_q" value="{{ filter_form.q.value|default:'' }}">
  </div>
  <div class="col-md-3">
    <label class="form-label small" for="id_status">Status</label>
    <select name="status" id="id_status" class="form-select">
      {% for value, label in filter_form.fields.status.choices %}
      <option value="{{ value }}"{% if filter_form.status.value == value %} selected{% endif %}>{{ label }}</option>
      {% endfor %}
    </select>
  </div>
  <div class="col-md-3 d-flex gap-2">
    <button type="submit" class="btn btn-outline-primary">Filter</button>
    <a href="{% url '__app__:list' %}" class="btn btn-link">Reset</a>
  </div>
</form>
<div class="card shadow-sm">
  <div class="table-responsive">
    <table class="table table-hover align-middle mb-0">
      <thead><tr><th>Title</th><th>Status</th><th>Owner</th><th>Updated</th></tr></thead>
      <tbody>
        {% for record in records %}
        <tr>
          <td><a href="{{ record.get_absolute_url }}">{{ record.title }}</a></td>
          <td>{% badge record.get_status_display %}</td>
          <td>{{ record.owner|person }}</td>
          <td>{{ record.updated_at|date:"M j, Y H:i" }}</td>
        </tr>
        {% empty %}
        <tr><td colspan="4" class="text-center text-body-secondary py-4">Nothing here yet.</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% if page_obj.has_other_pages %}<div class="card-footer bg-transparent">{% include "includes/pagination.html" %}</div>{% endif %}
</div>
{% endblock %}
