/**
 * fx_report.js
 * Sunartha ID — Multi-Currency Financial Reporting
 * Phase 1: Tab switching, lazy-load drilldown, pagination
 */

'use strict';

// ── Tab Switching ────────────────────────────────────────────────────────────

/**
 * Switch between CFO view and Accounting view.
 * Persists choice to localStorage.
 */
function switchView(viewName, clickedBtn) {
    document.querySelectorAll('.fx-view').forEach(function (el) {
        el.classList.add('d-none');
    });
    document.querySelectorAll('.fx-tab').forEach(function (btn) {
        btn.classList.remove('active');
    });

    var target = document.getElementById('view-' + viewName);
    if (target) target.classList.remove('d-none');
    if (clickedBtn) clickedBtn.classList.add('active');

    try {
        localStorage.setItem('fx_report_view', viewName);
    } catch (e) { /* ignore */ }
}

// Restore last tab on load
(function () {
    var savedView = null;
    try { savedView = localStorage.getItem('fx_report_view'); } catch (e) { }
    if (savedView) {
        var btn = document.querySelector(
            '[onclick="switchView(\'' + savedView + '\', this)"]'
        );
        if (btn) switchView(savedView, btn);
    }
})();


// ── Drilldown ────────────────────────────────────────────────────────────────

/**
 * Toggle drilldown row for an account line.
 * First open: fetch data from server (lazy load).
 */
function toggleDrilldown(row) {
    var accountId = row.getAttribute('data-account-id');
    var configId  = row.getAttribute('data-config-id');
    if (!accountId || !configId) return;

    var drillRow = document.getElementById('drill-' + accountId);
    if (!drillRow) return;

    var isOpen = !drillRow.classList.contains('d-none');

    // Toggle caret
    var caret = row.querySelector('.drill-caret');
    if (caret) {
        caret.classList.toggle('fa-caret-right', isOpen);
        caret.classList.toggle('fa-caret-down', !isOpen);
    }

    if (isOpen) {
        drillRow.classList.add('d-none');
        return;
    }

    drillRow.classList.remove('d-none');

    // Lazy load: only fetch if not loaded yet
    var content = drillRow.querySelector('.fx-drilldown-content');
    if (content && content.getAttribute('data-loaded') === '1') return;

    fetchDrilldown(configId, accountId, 1, 50, content);
}

/**
 * Fetch drilldown data from server with pagination.
 */
function fetchDrilldown(configId, accountId, page, pageSize, container) {
    if (!container) return;
    container.innerHTML = (
        '<div class="fx-loading text-center text-muted py-2">'
        + '<i class="fa fa-spinner fa-spin me-1"></i> Memuat data transaksi...'
        + '</div>'
    );

    var csrfToken = getCsrfToken();

    fetch('/acc_id_fx/drilldown', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify({
            jsonrpc: '2.0',
            method:  'call',
            params: {
                config_id:  parseInt(configId),
                account_id: parseInt(accountId),
                page:       page,
                page_size:  pageSize,
            },
        }),
    })
    .then(function (res) { return res.json(); })
    .then(function (data) {
        if (data.error || (data.result && data.result.error)) {
            var errMsg = data.error
                ? (data.error.data ? data.error.data.message : data.error.message)
                : data.result.error;
            container.innerHTML = (
                '<div class="text-danger p-2">'
                + '<i class="fa fa-exclamation-circle me-1"></i>'
                + escHtml(errMsg)
                + '</div>'
            );
            return;
        }

        var result = data.result;
        if (!result) {
            container.innerHTML = '<div class="text-muted p-2">Tidak ada data.</div>';
            return;
        }

        container.innerHTML = renderDrilldownTable(result);
        container.setAttribute('data-loaded', '1');
        container.setAttribute('data-config-id', configId);
        container.setAttribute('data-account-id', accountId);
    })
    .catch(function (err) {
        container.innerHTML = (
            '<div class="text-danger p-2">'
            + '<i class="fa fa-exclamation-circle me-1"></i>'
            + 'Error memuat data: ' + escHtml(err.message)
            + '</div>'
        );
    });
}

/**
 * Render drilldown table HTML from server result.
 */
function renderDrilldownTable(result) {
    var pg = result.pagination || {};
    var txns = result.transactions || [];

    var html = '<div class="fx-drill-wrapper">';

    // Info bar
    html += '<div class="d-flex justify-content-between align-items-center mb-2">';
    html += '<div class="small text-muted">';
    html += '<strong>' + escHtml(result.account_code) + ' — ' + escHtml(result.account_name) + '</strong>';
    html += ' | Kurs: Rp ' + fmtNum(result.rate_used, 2);
    html += ' (<span class="badge bg-primary">' + escHtml(result.rate_type || '') + '</span>)';
    if (result.is_override) {
        html += ' <span class="badge bg-warning text-dark">OVERRIDE: '
             + escHtml(result.override_reason || '') + '</span>';
    }
    html += '</div>';
    html += '<div class="small text-muted">';
    html += 'Menampilkan ' + ((pg.page - 1) * pg.page_size + 1)
         + '–' + Math.min(pg.page * pg.page_size, pg.total_count)
         + ' dari ' + pg.total_count + ' transaksi';
    html += '</div>';
    html += '</div>';

    if (txns.length === 0) {
        html += '<div class="text-muted py-2">Tidak ada transaksi.</div>';
    } else {
        html += '<table class="table table-sm table-hover fx-drill-table">';
        html += '<thead class="table-light"><tr>';
        html += '<th>Tanggal</th><th>No. Jurnal</th><th>Mitra</th>';
        html += '<th>Keterangan</th>';
        html += '<th class="text-end">Debit (IDR)</th>';
        html += '<th class="text-end">Kredit (IDR)</th>';
        html += '<th class="text-end">Saldo (IDR)</th>';
        html += '<th class="text-end text-muted">Val. Asing</th>';
        html += '</tr></thead><tbody>';

        txns.forEach(function (t) {
            html += '<tr>';
            html += '<td class="text-nowrap">' + escHtml(t.date || '') + '</td>';
            html += '<td class="text-nowrap small">' + escHtml(t.move_name || '') + '</td>';
            html += '<td class="small">' + escHtml(t.partner_name || '') + '</td>';
            html += '<td class="small">' + escHtml(t.label || '') + '</td>';
            html += '<td class="text-end">'
                 + (t.debit ? fmtNum(t.debit, 0) : '') + '</td>';
            html += '<td class="text-end">'
                 + (t.credit ? fmtNum(t.credit, 0) : '') + '</td>';
            html += '<td class="text-end fw-semibold">' + fmtNum(t.balance, 0) + '</td>';
            html += '<td class="text-end text-muted small">';
            if (t.amount_currency && t.currency_name && t.currency_name !== 'IDR') {
                html += fmtNum(t.amount_currency, 2) + ' ' + escHtml(t.currency_name);
            }
            html += '</td>';
            html += '</tr>';
        });

        html += '</tbody></table>';
    }

    // Pagination controls
    if (pg.total_pages > 1) {
        html += '<div class="d-flex justify-content-center gap-2 mt-2">';
        if (pg.has_prev) {
            html += '<button class="btn btn-sm btn-outline-secondary" '
                 + 'onclick="changeDrillPage(this, ' + (pg.page - 1) + ', ' + pg.page_size + ')">'
                 + '‹ Sebelumnya</button>';
        }
        html += '<span class="align-self-center small text-muted">Halaman '
             + pg.page + ' / ' + pg.total_pages + '</span>';
        if (pg.has_next) {
            html += '<button class="btn btn-sm btn-outline-secondary" '
                 + 'onclick="changeDrillPage(this, ' + (pg.page + 1) + ', ' + pg.page_size + ')">'
                 + 'Selanjutnya ›</button>';
        }
        html += '</div>';
    }

    html += '</div>';
    return html;
}

/**
 * Navigate to a different page in a drilldown panel.
 */
function changeDrillPage(btn, newPage, pageSize) {
    var wrapper = btn.closest('.fx-drilldown-content');
    if (!wrapper) return;
    var configId  = wrapper.getAttribute('data-config-id');
    var accountId = wrapper.getAttribute('data-account-id');
    if (!configId || !accountId) return;
    wrapper.removeAttribute('data-loaded');
    fetchDrilldown(configId, accountId, newPage, pageSize, wrapper);
}


// ── Utilities ────────────────────────────────────────────────────────────────

function escHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function fmtNum(num, decimals) {
    if (num === null || num === undefined || isNaN(num)) return '0';
    return parseFloat(num).toLocaleString('id-ID', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    });
}

function getCsrfToken() {
    // Odoo stores CSRF token in a cookie named 'csrf_token'
    var match = document.cookie.match(/csrf_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
}
