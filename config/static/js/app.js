/* Банкетные решения — клиентская логика Django-версии. */
(function () {
  'use strict';

  var $ = function (selector, root) { return (root || document).querySelector(selector); };
  var $$ = function (selector, root) { return Array.prototype.slice.call((root || document).querySelectorAll(selector)); };
  var money = function (value) { return new Intl.NumberFormat('ru-RU').format(Math.round(value)) + ' ₽'; };
  var csrf = function () {
    var input = $('input[name="csrfmiddlewaretoken"]');
    return input ? input.value : '';
  };

  function toast(text) {
    var el = $('#toast');
    if (!el) { return; }
    var label = el.querySelector('span');
    if (label) { label.textContent = text; }
    el.classList.add('show');
    window.clearTimeout(el._timer);
    el._timer = window.setTimeout(function () { el.classList.remove('show'); }, 3400);
  }

  function markField(input, invalid, message) {
    if (!input) { return; }
    var field = input.closest('.field') || input.closest('.form-section');
    if (field) { field.classList.toggle('invalid', !!invalid); }
    input.setAttribute('aria-invalid', invalid ? 'true' : 'false');
    if (!invalid) { return; }
    var error = field ? field.querySelector('.field-error') : null;
    if (error && message) { error.textContent = message; }
  }

  function digits(value) { return (value || '').replace(/\D/g, '').slice(0, 11); }

  function phoneOk(value) {
    var d = digits(value);
    return d.length === 11 && (d.charAt(0) === '7' || d.charAt(0) === '8');
  }

  function emailOk(value) { return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value || ''); }

  var templatesNode = document.getElementById('menu-templates');
  var templatesData = [];
  if (templatesNode) {
    try { templatesData = JSON.parse(templatesNode.textContent) || []; } catch (error) { templatesData = []; }
  }

  function syncTemplates(formatSelect, templateSelect, preserve) {
    if (!formatSelect || !templateSelect || !templatesData.length) { return; }
    var formatId = Number(formatSelect.value);
    var current = preserve ? templateSelect.value : '';
    var list = templatesData.filter(function (item) { return Number(item.format) === formatId; });
    templateSelect.innerHTML = '';
    templateSelect.add(new Option('Сет по умолчанию', ''));
    list.forEach(function (item) {
      templateSelect.add(new Option(item.name + ' · ' + item.output + ' г/чел.', item.id));
    });
    var keep = list.some(function (item) { return String(item.id) === current; });
    templateSelect.value = keep ? current : (list.length ? String(list[0].id) : '');
  }

  function maskPhone(input) {
    if (!input) { return; }
    input.addEventListener('input', function () {
      var d = digits(input.value);
      if (!d) { input.value = ''; return; }
      if (d.charAt(0) === '8') { d = '7' + d.slice(1); }
      if (d.charAt(0) !== '7') { d = '7' + d; }
      d = d.slice(0, 11);
      var out = '+7';
      if (d.length > 1) { out += ' (' + d.slice(1, 4); }
      if (d.length >= 4) { out += ') ' + d.slice(4, 7); }
      if (d.length >= 7) { out += '-' + d.slice(7, 9); }
      if (d.length >= 9) { out += '-' + d.slice(9, 11); }
      input.value = out;
    });
  }

  /* ------------------------------ меню-бургер ------------------------------ */
  var burger = $('.burger');
  if (burger) {
    burger.addEventListener('click', function () {
      var menu = $('#mobile-menu');
      if (!menu) { return; }
      var open = menu.classList.toggle('open');
      burger.setAttribute('aria-expanded', open ? 'true' : 'false');
      burger.setAttribute('aria-label', open ? 'Закрыть меню' : 'Открыть меню');
    });
  }

  $$('input[type="tel"]').forEach(maskPhone);

  /* --------------------------- клиентская валидация ------------------------- */
  function validateForm(form) {
    var firstInvalid = null;
    $$('input, textarea, select', form).forEach(function (input) {
      if (input.type === 'hidden' || input.type === 'submit' || input.type === 'checkbox') { return; }
      var value = (input.value || '').trim();
      var invalid = false;
      var message = '';

      if (input.required && !value) {
        invalid = true;
        message = 'Заполните это поле.';
      } else if (value && input.type === 'email' && !emailOk(value)) {
        invalid = true;
        message = 'Введите e-mail, например name@example.ru.';
      } else if (value && input.type === 'tel' && !phoneOk(value)) {
        invalid = true;
        message = 'Введите телефон в формате +7 (900) 000-00-00.';
      } else if (value && input.type === 'number') {
        var num = Number(value);
        var min = input.min !== '' ? Number(input.min) : null;
        var max = input.max !== '' ? Number(input.max) : null;
        if (isNaN(num) || (min !== null && num < min) || (max !== null && num > max)) {
          invalid = true;
          message = 'Введите число в допустимом диапазоне.';
        }
      } else if (value && input.dataset.minlength && value.length < Number(input.dataset.minlength)) {
        invalid = true;
        message = 'Слишком короткий текст: нужно минимум ' + input.dataset.minlength + ' символов.';
      }

      if (input.type === 'file' && input.files && input.files.length) {
        var file = input.files[0];
        var limit = 5 * 1024 * 1024;
        var allowed = /\.(png|jpe?g|webp|pdf)$/i;
        if (file.size > limit) {
          invalid = true;
          message = 'Файл больше 5 МБ. Выберите файл меньшего размера.';
        } else if (!allowed.test(file.name)) {
          invalid = true;
          message = 'Допустимые форматы: PNG, JPG, WEBP, PDF.';
        }
      }

      markField(input, invalid, message);
      if (invalid && !firstInvalid) { firstInvalid = input; }
    });

    var consent = form.querySelector('input[type="checkbox"][required]');
    if (consent && !consent.checked) {
      markField(consent, true, 'Подтвердите согласие на обработку данных.');
      if (!firstInvalid) { firstInvalid = consent; }
    }

    if (firstInvalid) {
      var box = $('#checkout-error');
      if (box) {
        box.hidden = false;
        var text = $('#checkout-error-text');
        if (text) { text.textContent = 'Проверьте выделенные поля.'; }
      }
      firstInvalid.focus();
      toast('Проверьте выделенные поля.');
      return false;
    }

    var box = $('#checkout-error');
    if (box) { box.hidden = true; }
    return true;
  }

  $$('form[novalidate]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      if (!validateForm(form)) {
        event.preventDefault();
      }
    });
  });

  /* ------------------------------- каталог: поиск -------------------------- */
  var searchInput = $('#q');
  var suggestions = $('#search-suggestions');
  if (searchInput && suggestions) {
    var timer = null;
    var controller = null;

    var close = function () {
      suggestions.hidden = true;
      suggestions.innerHTML = '';
    };

    var render = function (results) {
      suggestions.innerHTML = '';
      if (!results.length) {
        var empty = document.createElement('div');
        empty.className = 'suggestion-empty';
        empty.textContent = 'Ничего не найдено — попробуйте другой запрос.';
        suggestions.appendChild(empty);
      } else {
        results.forEach(function (item) {
          var link = document.createElement('a');
          link.href = item.url;
          var title = document.createElement('span');
          title.textContent = item.name + ' · ' + item.category;
          var price = document.createElement('span');
          price.className = 'suggestion-price';
          price.textContent = money(item.price);
          link.appendChild(title);
          link.appendChild(price);
          suggestions.appendChild(link);
        });
      }
      suggestions.hidden = false;
    };

    var search = function () {
      var query = (searchInput.value || '').trim();
      if (query.length < 2) { close(); return; }
      if (controller) { controller.abort(); }
      controller = new AbortController();
      suggestions.hidden = false;
      suggestions.innerHTML = '<div class="suggestion-empty">Ищем…</div>';
      fetch('/api/dishes/?q=' + encodeURIComponent(query), { signal: controller.signal })
        .then(function (response) { return response.json(); })
        .then(function (data) { render(data.results || []); })
        .catch(function (error) {
          if (error.name !== 'AbortError') { close(); }
        });
    };

    searchInput.addEventListener('input', function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(search, 260);
    });
    searchInput.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') { close(); }
    });
    document.addEventListener('click', function (event) {
      if (!event.target.closest('.search-box')) { close(); }
    });
  }

  /* ------------------------------ калькулятор AJAX ------------------------- */
  function postJson(url, payload) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf(),
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: JSON.stringify(payload)
    }).then(function (response) {
      return response.json().then(function (data) {
        return { status: response.status, data: data };
      });
    });
  }

  var calcForm = $('#calc-form');
  if (calcForm) {
    var apiUrl = calcForm.dataset.api;
    var loading = $('#calc-loading');
    var submit = calcForm.querySelector('button[type="submit"]');
    var calcFormat = calcForm.querySelector('[name="event_format"]');
    var calcTemplate = calcForm.querySelector('[name="menu_template"]');
    if (calcFormat && calcTemplate) {
      syncTemplates(calcFormat, calcTemplate, true);
      calcFormat.addEventListener('change', function () {
        syncTemplates(calcFormat, calcTemplate, false);
      });
    }

    var paint = function (data) {
      var set = function (selector, value) {
        var el = $(selector);
        if (el) { el.textContent = value; }
      };
      set('#s-guests', data.guests);
      set('#s-template', data.template);
      set('#s-price', money(data.price_per_guest));
      set('#s-menu', money(data.menu_total));
      set('#s-output', data.output_per_guest + ' г / чел.');
      set('#s-norm', data.norm + ' г / чел.');
      set('#s-decor', (data.decor_percent ? '+' : '') + data.decor_percent + ' %');
      set('#s-staff', money(data.staff_total));
      set('#s-tableware', money(data.tableware_total));
      set('#s-total', money(data.total));
      set('#s-waiters', data.waiters + ' чел.');
      set('#s-sets', data.tableware_sets + ' компл.');
      set('#s-waiters-2', data.waiters + ' чел.');
      set('#s-sets-2', data.tableware_sets + ' компл.');
      set('#s-deficit', data.deficit);

      var ok = $('#norm-ok');
      var warn = $('#norm-warn');
      if (ok) { ok.hidden = !data.output_ok; }
      if (warn) { warn.hidden = !!data.output_ok; }

      var kitchen = $('#kitchen-note');
      if (kitchen) { kitchen.hidden = !!data.kitchen_available; }
      set('#nearest-date', data.nearest_date || '—');

      var checkout = $('#to-checkout');
      if (checkout) {
        checkout.classList.toggle('is-disabled', !data.kitchen_available);
      }
    };

    var recalc = function () {
      var payload = {
        event_format: calcForm.querySelector('[name="event_format"]').value,
        menu_template: calcForm.querySelector('[name="menu_template"]') ? calcForm.querySelector('[name="menu_template"]').value : '',
        event_date: calcForm.querySelector('[name="event_date"]').value,
        guests: calcForm.querySelector('[name="guests"]').value,
        decor_percent: calcForm.querySelector('[name="decor_percent"]').value
      };
      if (loading) { loading.hidden = false; }
      if (submit) { submit.disabled = true; }
      postJson(apiUrl, payload)
        .then(function (result) {
          if (result.status === 200 && result.data.ok) {
            paint(result.data);
          } else if (result.data.errors) {
            Object.keys(result.data.errors).forEach(function (name) {
              var input = calcForm.querySelector('[name="' + name + '"]');
              var errors = result.data.errors[name] || [];
              markField(input, true, errors.length ? errors[0].message : 'Проверьте поле.');
            });
          }
        })
        .catch(function () { toast('Не удалось пересчитать смету. Проверьте соединение.'); })
        .finally(function () {
          if (loading) { loading.hidden = true; }
          if (submit) { submit.disabled = false; }
        });
    };

    calcForm.addEventListener('submit', function (event) {
      event.preventDefault();
      if (!validateForm(calcForm)) { return; }
      recalc();
      toast('Смета пересчитана на сервере');
    });

    var calcTimer = null;
    $$('select, input', calcForm).forEach(function (input) {
      input.addEventListener('change', function () {
        window.clearTimeout(calcTimer);
        calcTimer = window.setTimeout(recalc, 300);
      });
    });
  }
  /* --------------------------- смета на странице заказа -------------------- */
  var summary = $('#checkout-summary');
  var checkoutForm = $('#checkout-form');
  if (summary && checkoutForm) {
    var summaryApi = summary.dataset.api;
    var orderFormat = checkoutForm.querySelector('[name="event_format"]');
    var orderTemplate = checkoutForm.querySelector('[name="menu_template"]');
    if (orderFormat && orderTemplate) {
      syncTemplates(orderFormat, orderTemplate, true);
      orderFormat.addEventListener('change', function () {
        syncTemplates(orderFormat, orderTemplate, false);
      });
    }
    var updateSummary = function () {
      var payload = {
        event_format: checkoutForm.querySelector('[name="event_format"]').value,
        menu_template: orderTemplate ? orderTemplate.value : '',
        event_date: checkoutForm.querySelector('[name="event_date"]').value,
        guests: checkoutForm.querySelector('[name="guests"]').value,
        decor_percent: checkoutForm.querySelector('[name="decor_percent"]').value
      };
      if (!payload.event_format || !payload.event_date) { return; }
      summary.classList.add('is-loading');
      postJson(summaryApi, payload)
        .then(function (result) {
          if (result.status !== 200 || !result.data.ok) { return; }
          var data = result.data;
          var set = function (selector, value) {
            var el = $(selector);
            if (el) { el.textContent = value; }
          };
          set('#e-format', data.format);
          set('#e-template', data.template || '—');
          set('#e-price', new Intl.NumberFormat('ru-RU').format(data.price_per_guest));
          set('#e-guests', data.guests);
          set('#e-menu', money(data.menu_total));
          set('#e-decor', data.decor_percent);
          set('#e-decor-sum', money(data.decor_total));
          set('#e-staff', money(data.staff_total));
          set('#e-tableware', money(data.tableware_total));
          set('#e-total', money(data.total));
          set('#e-output', data.output_per_guest);
          var kitchen = $('#e-kitchen');
          if (kitchen) { kitchen.hidden = !!data.kitchen_available; }
          set('#e-nearest', data.nearest_date || '—');
          var note = $('#e-output-note');
          if (note) {
            note.classList.toggle('notice-success', !!data.output_ok);
            note.classList.toggle('notice-warning', !data.output_ok);
            var extra = $('#e-output-extra');
            if (extra) {
              extra.textContent = data.output_ok
                ? ''
                : ' Не хватает ' + data.deficit + ' г/чел.';
            }
          }
        })
        .catch(function () { /* тихо: смета пересчитается на сервере при отправке */ })
        .finally(function () { summary.classList.remove('is-loading'); });
    };

    $$('select, input', checkoutForm).forEach(function (input) {
      input.addEventListener('change', updateSummary);
    });
  }

  var fileInput = $('#id_sketch');
  if (fileInput) {
    fileInput.addEventListener('change', function () {
      var file = fileInput.files && fileInput.files[0];
      if (!file) { return; }
      if (file.size > 5 * 1024 * 1024) {
        markField(fileInput, true, 'Файл больше 5 МБ. Выберите файл меньшего размера.');
        toast('Файл больше 5 МБ');
      } else {
        markField(fileInput, false);
        toast('Файл выбран: ' + file.name);
      }
    });
  }

  /* --------------------------- подтверждение отмены ------------------------ */
  $$('[data-confirm]').forEach(function (element) {
    element.addEventListener('click', function (event) {
      if (!window.confirm(element.dataset.confirm)) {
        event.preventDefault();
      }
    });
  });

  /* ------------------------------- печатная форма -------------------------- */
  $$('[data-print]').forEach(function (button) {
    button.addEventListener('click', function () { window.print(); });
  });
}());
