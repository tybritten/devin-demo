{% extends "base.html" %}
{% load crispy_forms_tags %}
{% block title %}{% if record %}Edit {{ record }}{% else %}New __model_title__{% endif %}{% endblock %}
{% block content %}
<nav aria-label="breadcrumb"><ol class="breadcrumb">
  <li class="breadcrumb-item"><a href="{% url '__app__:list' %}">__Title__</a></li>
  {% if record %}<li class="breadcrumb-item"><a href="{{ record.get_absolute_url }}">{{ record }}</a></li>{% endif %}
  <li class="breadcrumb-item active" aria-current="page">{% if record %}Edit{% else %}New{% endif %}</li>
</ol></nav>
<h1 class="h3 mb-4">{% if record %}Edit {{ record }}{% else %}New __model_title__{% endif %}</h1>
<div class="card shadow-sm" style="max-width: 48rem">
  <div class="card-body">
    <form method="post" novalidate>
      {% csrf_token %}
      {{ form|crispy }}
      <div class="d-flex gap-2">
        <button type="submit" class="btn btn-primary">Save</button>
        <a href="{% if record %}{{ record.get_absolute_url }}{% else %}{% url '__app__:list' %}{% endif %}" class="btn btn-outline-secondary">Cancel</a>
      </div>
    </form>
  </div>
</div>
{% endblock %}
