(() => {
  const bootEl = document.getElementById("notesPageBootstrap");
  if (!bootEl) {
    return;
  }

  let boot = {};
  try {
    boot = JSON.parse(bootEl.textContent || "{}");
  } catch (error) {
    console.error("Failed to parse notes page bootstrap data.", error);
    return;
  }

  const initialNotes = Array.isArray(boot.notes) ? boot.notes : [];
      const queryParams = new URLSearchParams(window.location.search);
      const requestedNoteId = Number(queryParams.get('note_id') || 0);
      const noteStore = new Map(initialNotes.map((note) => [note.id, note]));
      const noteResultsEl = document.getElementById('noteResults');
      const noteSearchInput = document.getElementById('noteSearchInput');
      const noteCount = document.getElementById('noteCount');
      const noteBatchExportBar = document.getElementById('noteBatchExportBar');
      const noteBatchSelectionTitle = document.getElementById('noteBatchSelectionTitle');
      const clearNoteSelectionBtn = document.getElementById('clearNoteSelectionBtn');
      const batchExportNotesBtn = document.getElementById('batchExportNotesBtn');
      const stackFilterList = document.getElementById('stackFilterList');
      const noteTagFilterList = document.getElementById('noteTagFilterList');
      const statusFilterList = document.getElementById('statusFilterList');
      const sessionSearchSection = document.getElementById('sessionSearchSection');
      const sessionResultCount = document.getElementById('sessionResultCount');
      const sessionSearchResults = document.getElementById('sessionSearchResults');
      const editShell = document.getElementById('editShell');
      const editModalTitle = document.getElementById('editModalTitle');
      const editAppendSummaryCard = document.getElementById('editAppendSummaryCard');
      const editAppendSummaryTitle = document.getElementById('editAppendSummaryTitle');
      const editAppendSummaryText = document.getElementById('editAppendSummaryText');
      const editAppendSummaryMeta = document.getElementById('editAppendSummaryMeta');
      const editAppendSummarySections = document.getElementById('editAppendSummarySections');
      const editAppendTimelineCard = document.getElementById('editAppendTimelineCard');
      const editAppendTimelineTitle = document.getElementById('editAppendTimelineTitle');
      const editAppendTimelineOverview = document.getElementById('editAppendTimelineOverview');
      const editAppendTimelineOverviewGrid = document.getElementById('editAppendTimelineOverviewGrid');
      const editAppendTimelineOverviewHint = document.getElementById('editAppendTimelineOverviewHint');
      const editAppendTimelineSearchInput = document.getElementById('editAppendTimelineSearchInput');
      const editAppendTimelineSearchResetBtn = document.getElementById('editAppendTimelineSearchResetBtn');
      const editAppendTimelineFilters = document.getElementById('editAppendTimelineFilters');
      const editAppendTimelineList = document.getElementById('editAppendTimelineList');
      const editNoteForm = document.getElementById('editNoteForm');
      const editTitle = document.getElementById('editTitle');
      const editStatus = document.getElementById('editStatus');
      const editTags = document.getElementById('editTags');
      const editProblem = document.getElementById('editProblem');
      const editRootCause = document.getElementById('editRootCause');
      const editSolution = document.getElementById('editSolution');
      const editTakeaways = document.getElementById('editTakeaways');
      const editNotice = document.getElementById('editNotice');
      const deleteEditBtn = document.getElementById('deleteEditBtn');
      const exportEditBtn = document.getElementById('exportEditBtn');
      const saveEditBtn = document.getElementById('saveEditBtn');
      const sourceShell = document.getElementById('sourceShell');
      const sourceModalTitle = document.getElementById('sourceModalTitle');
      const sourceModalHint = document.getElementById('sourceModalHint');
      const sourceModalList = document.getElementById('sourceModalList');
      const sessionShell = document.getElementById('sessionShell');
      const sessionModalTitle = document.getElementById('sessionModalTitle');
      const sessionModalHint = document.getElementById('sessionModalHint');
      const sessionModalList = document.getElementById('sessionModalList');
      const appendPreviewShell = document.getElementById('appendPreviewShell');
      const appendPreviewTitle = document.getElementById('appendPreviewTitle');
      const appendPreviewHint = document.getElementById('appendPreviewHint');
      const appendPreviewSummary = document.getElementById('appendPreviewSummary');
      const appendPreviewSections = document.getElementById('appendPreviewSections');
      const appendPreviewNotice = document.getElementById('appendPreviewNotice');
      const confirmAppendPreviewBtn = document.getElementById('confirmAppendPreviewBtn');
      const NOTES_PREFS_KEY = 'knowledgebase.notes.filters';
      const EDIT_DRAFT_KEY_PREFIX = 'knowledgebase.notes.editDraft.';
      const APPEND_SUMMARY_KEY_PREFIX = 'knowledgebase.notes.appendSummary.';
      const noteStatusMeta = {
        all: '全部',
        draft: '草稿',
        reviewed: '已复核',
        published: '已发布'
      };
      const APPEND_FIELD_ELEMENTS = {
        problem: () => editProblem,
        root_cause: () => editRootCause,
        solution: () => editSolution,
        key_takeaways: () => editTakeaways,
      };

      let currentNotes = [...initialNotes];
      let currentSessionHits = [];
      let selectedNoteIds = [];
      let activeEditNoteId = null;
      let activeStackFilter = 'all';
      let activeNoteTagFilter = 'all';
      let activeStatusFilter = 'all';
      let activeAppendPreview = null;
      let activeAppendTimelineFilter = 'all';
      let activeAppendTimelineQuery = '';
      let activeAppendTimelineEvents = [];
      let activeAppendTimelineEventId = null;
      let activeAppendTimelineExpandedIds = new Set();

      function noteStatusLabel(status) {
        return noteStatusMeta[status] || String(status || '');
      }

      function toggleNoteSelection(noteId) {
        if (selectedNoteIds.includes(noteId)) {
          selectedNoteIds = selectedNoteIds.filter((item) => item !== noteId);
        } else {
          selectedNoteIds = [...selectedNoteIds, noteId];
        }
      }

      function clearNoteSelection() {
        selectedNoteIds = [];
      }

      function pruneSelectedNotes(notes) {
        const visibleIds = new Set((notes || []).map((note) => Number(note.id)));
        selectedNoteIds = selectedNoteIds.filter((noteId) => visibleIds.has(Number(noteId)));
      }

      function renderNoteBatchBar() {
        const count = selectedNoteIds.length;
        noteBatchExportBar.hidden = count === 0;
        noteBatchSelectionTitle.textContent = `已选中 ${count} 篇笔记`;
        batchExportNotesBtn.disabled = count === 0;
        clearNoteSelectionBtn.disabled = count === 0;
      }

      function normalizeStackFilter(value) {
        return typeof value === 'string' && value.trim() ? value.trim() : 'all';
      }

      function normalizeNoteTagFilter(value) {
        return typeof value === 'string' && value.trim() ? value.trim() : 'all';
      }

      function normalizeStatusFilter(value) {
        return ['all', 'draft', 'reviewed', 'published'].includes(value) ? value : 'all';
      }

      function parseTagInput(value) {
        return String(value || '')
          .split(/[,\uFF0C]/)
          .map((item) => item.trim())
          .filter(Boolean);
      }

      function loadNotesPreferences() {
        try {
          const raw = window.localStorage.getItem(NOTES_PREFS_KEY);
          if (!raw) {
            return;
          }

          const prefs = JSON.parse(raw);
          noteSearchInput.value = typeof prefs?.search === 'string' ? prefs.search : '';
          activeStackFilter = normalizeStackFilter(prefs?.stackFilter);
          activeNoteTagFilter = normalizeNoteTagFilter(prefs?.noteTagFilter);
          activeStatusFilter = normalizeStatusFilter(String(prefs?.statusFilter || 'all'));
        } catch (error) {
          noteSearchInput.value = '';
          activeStackFilter = 'all';
          activeNoteTagFilter = 'all';
          activeStatusFilter = 'all';
        }
      }

      function persistNotesPreferences() {
        try {
          window.localStorage.setItem(
            NOTES_PREFS_KEY,
            JSON.stringify({
              search: noteSearchInput.value,
              stackFilter: normalizeStackFilter(activeStackFilter),
              noteTagFilter: normalizeNoteTagFilter(activeNoteTagFilter),
              statusFilter: normalizeStatusFilter(activeStatusFilter)
            })
          );
        } catch (error) {
          // Ignore storage failures in private mode or restrictive environments.
        }
      }

      function editDraftKey(noteId) {
        return `${EDIT_DRAFT_KEY_PREFIX}${noteId}`;
      }

      function getEditFormData() {
        return {
          title: editTitle.value,
          status: editStatus.value,
          tags: editTags.value,
          problem: editProblem.value,
          root_cause: editRootCause.value,
          solution: editSolution.value,
          key_takeaways: editTakeaways.value
        };
      }

      function fillEditForm(note) {
        editTitle.value = note.title || '';
        editStatus.value = note.status || 'draft';
        editTags.value = (note.tags || []).join(', ');
        editProblem.value = note.problem || '';
        editRootCause.value = note.root_cause || '';
        editSolution.value = note.solution || '';
        editTakeaways.value = note.key_takeaways || '';
      }

      function hasEditChanges(noteId = activeEditNoteId, fields = getEditFormData()) {
        if (!noteId) {
          return false;
        }

        const note = noteStore.get(noteId);
        if (!note) {
          return Object.values(fields).some((value) => String(value || '').trim());
        }

        return (
          String(fields.title || '').trim() !== String(note.title || '').trim() ||
          String(fields.status || '') !== String(note.status || '') ||
          parseTagInput(fields.tags || '').join('|') !== (note.tags || []).join('|') ||
          String(fields.problem || '').trim() !== String(note.problem || '').trim() ||
          String(fields.root_cause || '').trim() !== String(note.root_cause || '').trim() ||
          String(fields.solution || '').trim() !== String(note.solution || '').trim() ||
          String(fields.key_takeaways || '').trim() !== String(note.key_takeaways || '').trim()
        );
      }

      function loadEditDraft(noteId) {
        try {
          const raw = window.localStorage.getItem(editDraftKey(noteId));
          if (!raw) {
            return null;
          }

          const draft = JSON.parse(raw);
          if (!draft || !hasEditChanges(noteId, draft.fields || {})) {
            return null;
          }
          return draft.fields;
        } catch (error) {
          return null;
        }
      }

      function persistEditDraft() {
        if (!activeEditNoteId) {
          return;
        }

        const fields = getEditFormData();
        try {
          if (!hasEditChanges(activeEditNoteId, fields)) {
            window.localStorage.removeItem(editDraftKey(activeEditNoteId));
            return;
          }

          window.localStorage.setItem(
            editDraftKey(activeEditNoteId),
            JSON.stringify({
              note_id: activeEditNoteId,
              fields
            })
          );
        } catch (error) {
          // Ignore storage failures in private mode or restrictive environments.
        }
      }

      function clearEditDraft(noteId) {
        if (!noteId) {
          return;
        }
        try {
          window.localStorage.removeItem(editDraftKey(noteId));
        } catch (error) {
          // Ignore storage failures in private mode or restrictive environments.
        }
      }

      function takeAppendSummary(noteId) {
        if (!noteId) {
          return null;
        }
        const storageKey = `${APPEND_SUMMARY_KEY_PREFIX}${noteId}`;
        try {
          const raw = window.localStorage.getItem(storageKey);
          if (!raw) {
            return null;
          }
          window.localStorage.removeItem(storageKey);
          const payload = JSON.parse(raw);
          return payload?.summary || null;
        } catch (error) {
          return null;
        }
      }

      function persistAppendSummary(noteId, summary) {
        const resolvedNoteId = Number(noteId || 0);
        if (!resolvedNoteId || !summary) {
          return;
        }
        try {
          window.localStorage.setItem(
            `${APPEND_SUMMARY_KEY_PREFIX}${resolvedNoteId}`,
            JSON.stringify({
              note_id: resolvedNoteId,
              summary,
              saved_at: Date.now()
            })
          );
        } catch (error) {
          // Ignore storage failures in private mode or restrictive environments.
        }
      }

      function hideAppendSummaryCard() {
        editAppendSummaryCard.hidden = true;
        editAppendSummaryTitle.textContent = '刚刚追加进来的变化';
        editAppendSummaryText.textContent = '这里会提示这次追加带来的主要变化。';
        editAppendSummaryMeta.innerHTML = '';
        editAppendSummarySections.innerHTML = '';
        Object.values(APPEND_FIELD_ELEMENTS).forEach((resolve) => {
          const field = resolve();
          field?.closest('.field')?.classList.remove('field-highlight');
        });
      }

      function hideAppendTimelineCard() {
        editAppendTimelineCard.hidden = true;
        editAppendTimelineTitle.textContent = '这篇笔记最近并入过哪些内容';
        editAppendTimelineOverviewGrid.innerHTML = '';
        editAppendTimelineOverviewHint.textContent = '';
        editAppendTimelineSearchInput.value = '';
        editAppendTimelineFilters.innerHTML = '';
        editAppendTimelineList.innerHTML = '';
        activeAppendTimelineFilter = 'all';
        activeAppendTimelineQuery = '';
        activeAppendTimelineEvents = [];
        activeAppendTimelineEventId = null;
        activeAppendTimelineExpandedIds = new Set();
      }

      function renderAppendTimelineOverview(events) {
        if (!Array.isArray(events) || !events.length) {
          editAppendTimelineOverviewGrid.innerHTML = '';
          editAppendTimelineOverviewHint.textContent = '';
          return;
        }

        const totalEvents = events.length;
        const totalAddedSources = events.reduce((total, event) => total + Number(event.source_count_added || 0), 0);
        const latestEvent = events[0];
        const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
        const activeThisWeek = events.filter((event) => {
          const timestamp = Date.parse(String(event.created_at || '').replace(' ', 'T'));
          return Number.isFinite(timestamp) && timestamp >= weekAgo;
        }).length;

        const sourceCounts = new Map();
        for (const event of events) {
          const label = String(event.source || '').trim() || '手动补充';
          sourceCounts.set(label, Number(sourceCounts.get(label) || 0) + 1);
        }
        const topSources = [...sourceCounts.entries()]
          .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0], 'zh-CN'))
          .slice(0, 3);

        const metrics = [
          { label: '累计追加', value: `${totalEvents} 次`, note: '这篇笔记被持续补充的次数' },
          { label: '总新增来源', value: `${totalAddedSources} 条`, note: '累计并入的原始消息来源' },
          { label: '最近追加', value: String(latestEvent.created_at || '未记录'), note: '最近一次补充发生的时间' },
          { label: '近 7 天活跃', value: `${activeThisWeek} 次`, note: '最近一周内发生的补充次数' },
        ];

        editAppendTimelineOverviewGrid.innerHTML = metrics.map((item) => `
          <article class="append-overview-item">
            <span class="eyebrow">${escapeHtml(item.label)}</span>
            <strong>${escapeHtml(item.value)}</strong>
            <span class="panel-text">${escapeHtml(item.note)}</span>
          </article>
        `).join('');
        editAppendTimelineOverviewHint.textContent = topSources.length
          ? `主要来源：${topSources.map(([label, count]) => `${label} ${count} 次`).join(' / ')}`
          : '目前还没有可识别的主要来源。';
      }

      function renderAppendSummaryCard(summary, options = {}) {
        if (!summary) {
          hideAppendSummaryCard();
          return;
        }

        const title = String(options.title || '这次追加带来的变化');
        const summaryText = String(options.summaryText || summary.summary_text || '这次追加已经并入目标笔记。');
        const meta = [];
        if (options.metaLead) {
          meta.push(`<span class="mini-tag stack-tag">${escapeHtml(options.metaLead)}</span>`);
        }
        if (Number(summary.source_count_added || 0) > 0) {
          meta.push(`<span class="mini-tag note-tag">新增 ${escapeHtml(summary.source_count_added)} 条来源</span>`);
        }
        for (const section of summary.changed_sections || []) {
          meta.push(`<span class="mini-tag stack-tag">${escapeHtml(section)}</span>`);
        }
        for (const tag of summary.added_tags || []) {
          meta.push(`<span class="mini-tag note-tag">标签 ${escapeHtml(tag)}</span>`);
        }
        const sectionBlocks = (summary.section_updates || []).map((item) => `
          <section class="append-summary-block">
            <h4>${escapeHtml(item.label || '')}</h4>
            <p>${escapeHtml(item.incoming_text || '')}</p>
          </section>
        `);

        editAppendSummaryCard.hidden = false;
        editAppendSummaryTitle.textContent = title;
        editAppendSummaryText.textContent = summaryText;
        editAppendSummaryMeta.innerHTML = meta.join('');
        editAppendSummarySections.innerHTML = sectionBlocks.join('');
        Object.values(APPEND_FIELD_ELEMENTS).forEach((resolve) => {
          const field = resolve();
          field?.closest('.field')?.classList.remove('field-highlight');
        });
        for (const item of summary.section_updates || []) {
          const field = APPEND_FIELD_ELEMENTS[item.field]?.();
          field?.closest('.field')?.classList.add('field-highlight');
        }
      }

      function focusAppendTimelineEvent(eventId, options = {}) {
        const targetId = Number(eventId || 0);
        if (!targetId) {
          return;
        }

        const event = activeAppendTimelineEvents.find((item) => Number(item.id) === targetId);
        if (!event) {
          return;
        }

        activeAppendTimelineEventId = targetId;
        if (event.section_updates?.length) {
          activeAppendTimelineExpandedIds.add(targetId);
        }
        renderAppendTimeline(activeAppendTimelineEvents);
        renderAppendSummaryCard(
          {
            source_count_added: event.source_count_added,
            changed_sections: event.changed_sections,
            added_tags: event.added_tags,
            section_updates: event.section_updates,
            summary_text: event.summary_text,
          },
          {
            title: `回看：${event.origin_label || '这次并入变化'}`,
            summaryText: event.summary_text || '这次并入了新的补充内容。',
            metaLead: event.created_at || '',
          }
        );

        const firstUpdatedFieldName = event.section_updates?.[0]?.field;
        const firstUpdatedField = APPEND_FIELD_ELEMENTS[firstUpdatedFieldName]?.();
        const scrollTarget = firstUpdatedField?.closest('.field') || editAppendSummaryCard;
        if (!options.skipScroll && scrollTarget?.scrollIntoView) {
          scrollTarget.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }

      function appendTimelineFilterMeta(events) {
        const counters = new Map();
        for (const event of events || []) {
          const source = String(event.source || '').trim();
          const key = source ? `source:${source}` : 'source:manual';
          const label = source || '手动补充';
          counters.set(key, {
            key,
            label,
            count: Number(counters.get(key)?.count || 0) + 1,
          });
        }

        return [
          { key: 'all', label: '全部', count: Array.isArray(events) ? events.length : 0 },
          ...[...counters.values()].sort((left, right) => left.label.localeCompare(right.label, 'zh-CN')),
        ];
      }

      function filteredAppendTimelineEvents() {
        let filtered = [...activeAppendTimelineEvents];
        if (activeAppendTimelineFilter !== 'all') {
          const [, sourceLabel = ''] = String(activeAppendTimelineFilter || '').split(':');
          if (sourceLabel === 'manual') {
            filtered = filtered.filter((event) => !String(event.source || '').trim());
          } else {
            filtered = filtered.filter((event) => String(event.source || '').trim() === sourceLabel);
          }
        }

        const query = String(activeAppendTimelineQuery || '').trim().toLowerCase();
        if (!query) {
          return filtered;
        }

        return filtered.filter((event) => {
          const haystack = [
            event.origin_label,
            event.source,
            event.session_id,
            event.summary_text,
            ...(event.changed_sections || []),
            ...(event.added_tags || []),
            ...(event.section_updates || []).map((item) => `${item.label || ''} ${item.incoming_text || ''}`),
          ].join(' ').toLowerCase();
          return haystack.includes(query);
        });
      }

      function renderAppendTimelineFilters(events) {
        const items = appendTimelineFilterMeta(events);
        editAppendTimelineFilters.innerHTML = items.map((item) => `
          <button
            type="button"
            class="tag-filter-btn${item.key === activeAppendTimelineFilter ? ' is-active' : ''}"
            data-append-timeline-filter="${escapeHtml(item.key)}"
          >
            ${escapeHtml(item.label)} · ${escapeHtml(item.count)}
          </button>
        `).join('');
      }

      function appendTimelineDateGroups(events) {
        const groups = new Map();
        for (const event of events || []) {
          const rawDate = String(event.created_at || '').trim();
          const dateKey = rawDate ? rawDate.slice(0, 10) : '未记录日期';
          if (!groups.has(dateKey)) {
            groups.set(dateKey, []);
          }
          groups.get(dateKey).push(event);
        }
        return [...groups.entries()];
      }

      function renderAppendTimeline(events) {
        if (!Array.isArray(events) || !events.length) {
          hideAppendTimelineCard();
          return;
        }

        activeAppendTimelineEvents = [...events];
        const visibleEvents = filteredAppendTimelineEvents();
        const timelineQuery = String(activeAppendTimelineQuery || '').trim();
        editAppendTimelineCard.hidden = false;
        editAppendTimelineTitle.textContent = `这篇笔记最近并入过 ${events.length} 次补充`;
        renderAppendTimelineOverview(events);
        renderAppendTimelineFilters(events);
        const groups = appendTimelineDateGroups(visibleEvents);
        editAppendTimelineList.innerHTML = groups.map(([dateKey, groupItems]) => `
          <section class="append-timeline-group">
            <header class="append-timeline-group-head">
              <h4>${escapeHtml(dateKey)}</h4>
              <span class="pill">${escapeHtml(groupItems.length)} 次补充</span>
            </header>
            ${groupItems.map((event) => {
          const changedSections = (event.changed_sections || [])
            .map((section) => `<span class="mini-tag stack-tag">${highlightText(section, timelineQuery)}</span>`)
            .join('');
          const addedTags = (event.added_tags || [])
            .map((tag) => `<span class="mini-tag note-tag">标签 ${highlightText(tag, timelineQuery)}</span>`)
            .join('');
          const action = event.source && event.session_id
            ? `
              <button
                type="button"
                class="ghost-button open-append-history-session"
                data-source="${escapeHtml(event.source)}"
                data-session-id="${escapeHtml(event.session_id)}"
                data-title="${escapeHtml(event.origin_label)}"
              >
                查看这次会话
              </button>
            `
            : '';
          const focusAction = event.section_updates?.length
            ? `
              <button
                type="button"
                class="secondary-btn focus-append-history-event"
                data-append-event-id="${escapeHtml(event.id)}"
              >
                定位新增段落
              </button>
            `
            : '';
          const undoAction = event.can_undo
            ? `
              <button
                type="button"
                class="danger-button undo-append-history-event"
                data-append-event-id="${escapeHtml(event.id)}"
              >
                撤销这次追加
              </button>
            `
            : '';
          const isExpanded = activeAppendTimelineExpandedIds.has(Number(event.id));
          const toggleAction = event.section_updates?.length
            ? `
              <button
                type="button"
                class="ghost-button toggle-append-history-event"
                data-append-event-id="${escapeHtml(event.id)}"
              >
                ${isExpanded ? '收起新增内容' : '展开新增内容'}
              </button>
            `
            : '';
          const detailBlocks = isExpanded
            ? `
              <div class="append-timeline-details">
                ${(event.section_updates || []).map((item) => `
                  <section class="append-timeline-detail">
                    <h5>${highlightText(item.label || '', timelineQuery)}</h5>
                    <p>${highlightText(item.incoming_text || '', timelineQuery)}</p>
                  </section>
                `).join('')}
              </div>
            `
            : '';
          return `
            <article class="append-timeline-item${Number(event.id) === Number(activeAppendTimelineEventId) ? ' is-active' : ''}">
              <header class="browser-head">
                <div>
                  <h4>${highlightText(event.origin_label || '追加补充', timelineQuery)}</h4>
                  <div class="inline-meta inline-meta-tight">
                    <span>${escapeHtml(event.created_at || '')}</span>
                    <span>新增 ${escapeHtml(event.source_count_added || 0)} 条来源</span>
                  </div>
                </div>
                <div class="inline-actions">
                  ${undoAction}
                  ${focusAction}
                  ${toggleAction}
                  ${action}
                </div>
              </header>
              <p class="panel-text">${highlightText(event.summary_text || '这次并入了新的补充内容。', timelineQuery)}</p>
              <div class="note-tag-row">
                ${changedSections}
                ${addedTags}
              </div>
              ${detailBlocks}
            </article>
          `;
        }).join('')}
          </section>
        `).join('');
        if (!visibleEvents.length) {
          editAppendTimelineList.innerHTML = `<p class="source-empty">${timelineQuery ? '当前筛选和关键词下没有追加记录。' : '当前来源筛选下没有追加记录。'}</p>`;
        }
      }

      async function loadAppendHistory(noteId) {
        if (!noteId) {
          hideAppendTimelineCard();
          return;
        }

        activeAppendTimelineFilter = 'all';
        activeAppendTimelineQuery = '';
        activeAppendTimelineEventId = null;
        activeAppendTimelineExpandedIds = new Set();
        editAppendTimelineCard.hidden = false;
        editAppendTimelineTitle.textContent = '正在载入追加时间线...';
        editAppendTimelineSearchInput.value = '';
        editAppendTimelineFilters.innerHTML = '';
        editAppendTimelineList.innerHTML = '<p class="source-empty">正在加载这篇笔记的追加历史...</p>';
        try {
          const resp = await fetch(`/api/notes/${noteId}/history`);
          if (!resp.ok) {
            throw new Error(`加载失败: ${resp.status}`);
          }
          const data = await resp.json();
          renderAppendTimeline(data.items || []);
        } catch (error) {
          editAppendTimelineCard.hidden = false;
          editAppendTimelineTitle.textContent = '追加时间线';
          editAppendTimelineList.innerHTML = `<p class="source-empty">${escapeHtml(error.message || '加载追加历史失败，请稍后再试。')}</p>`;
        }
      }

      function shouldWarnBeforeClosingEdit() {
        return !editShell.hidden && hasEditChanges();
      }

      function requestCloseEditModal() {
        if (
          shouldWarnBeforeClosingEdit() &&
          !window.confirm('当前笔记有未保存修改，关闭后仍可稍后恢复本地草稿。确定关闭吗？')
        ) {
          return;
        }
        closeEditModal();
      }

      function escapeHtml(value) {
        return String(value || '')
          .replaceAll('&', '&amp;')
          .replaceAll('<', '&lt;')
          .replaceAll('>', '&gt;')
          .replaceAll('"', '&quot;')
          .replaceAll("'", '&#39;');
      }

      function escapeRegExp(value) {
        return String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      }

      function highlightText(value, keyword) {
        const text = String(value || '');
        const query = String(keyword || '').trim();
        if (!query) {
          return escapeHtml(text);
        }

        const regex = new RegExp(escapeRegExp(query), 'ig');
        let lastIndex = 0;
        let result = '';

        for (const match of text.matchAll(regex)) {
          const start = match.index ?? 0;
          const matched = match[0] || '';
          result += escapeHtml(text.slice(lastIndex, start));
          result += `<mark class="search-hit">${escapeHtml(matched)}</mark>`;
          lastIndex = start + matched.length;
        }

        result += escapeHtml(text.slice(lastIndex));
        return result;
      }

      function clip(value, maxLength = 180) {
        const text = String(value || '').trim();
        return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
      }

      async function downloadNotesMarkdownZip(noteIds) {
        const resolvedIds = [...new Set((noteIds || []).map((noteId) => Number(noteId)).filter(Boolean))];
        if (!resolvedIds.length) {
          return;
        }

        const resp = await fetch('/api/notes/export.zip', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ note_ids: resolvedIds })
        });
        if (!resp.ok) {
          const data = await resp.json().catch(() => ({}));
          throw new Error(data?.detail || `批量导出失败: ${resp.status}`);
        }

        const blob = await resp.blob();
        const url = window.URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = 'notes-export.zip';
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        window.URL.revokeObjectURL(url);
      }

      function downloadNoteMarkdown(noteId) {
        const resolvedNoteId = Number(noteId || 0);
        if (!resolvedNoteId) {
          return;
        }
        const anchor = document.createElement('a');
        anchor.href = `/api/notes/${encodeURIComponent(resolvedNoteId)}/export.md`;
        anchor.rel = 'noopener';
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
      }

      function normalizeAppendText(value) {
        return String(value || '')
          .replace(/\s+/g, ' ')
          .trim()
          .toLowerCase();
      }

      function analyzeAppendSection(existing, incoming) {
        const existingText = String(existing || '').trim();
        const incomingText = String(incoming || '').trim();
        const normalizedExisting = normalizeAppendText(existingText);
        const normalizedIncoming = normalizeAppendText(incomingText);

        if (!normalizedIncoming) {
          return {
            changed: false,
            status: '无新增',
            reason: '这次生成的草稿在这一栏没有稳定内容。',
            existing: existingText,
            incoming: '',
          };
        }
        if (!normalizedExisting) {
          return {
            changed: true,
            status: '会新增',
            reason: '目标笔记这一栏还是空的，这次会直接补进去。',
            existing: '',
            incoming: incomingText,
          };
        }
        if (normalizedExisting.includes(normalizedIncoming)) {
          return {
            changed: false,
            status: '已覆盖',
            reason: '这段内容已经出现在目标笔记里，不会重复追加。',
            existing: existingText,
            incoming: incomingText,
          };
        }
        return {
          changed: true,
          status: '会追加',
          reason: '这段内容会作为新的补充追加到目标笔记。',
          existing: existingText,
          incoming: incomingText,
        };
      }

      function groupSessionHits(items) {
        const groups = new Map();
        for (const item of items || []) {
          const key = item.session_id
            ? `${item.source}::${item.session_id}`
            : `message:${item.id}`;
          const existing = groups.get(key);
          const snippet = clip(item.summary || item.content || '', 180);

          if (!existing) {
            groups.set(key, {
              key,
              source: item.source || 'unknown',
              session_id: item.session_id || '',
              latest_created_at: item.created_at || '',
              match_count: 1,
              snippets: snippet ? [snippet] : [],
              roles: item.role ? [item.role] : [],
              preview_title: item.session_id
                ? `${item.source} / ${item.session_id}`
                : `${item.source} / 消息 ${item.id}`
            });
            continue;
          }

          existing.match_count += 1;
          if (item.created_at && String(item.created_at) > String(existing.latest_created_at || '')) {
            existing.latest_created_at = item.created_at;
          }
          if (snippet && !existing.snippets.includes(snippet) && existing.snippets.length < 3) {
            existing.snippets.push(snippet);
          }
          if (item.role && !existing.roles.includes(item.role)) {
            existing.roles.push(item.role);
          }
        }

        return [...groups.values()].sort((left, right) => {
          const matchGap = Number(right.match_count || 0) - Number(left.match_count || 0);
          if (matchGap !== 0) {
            return matchGap;
          }
          return String(right.latest_created_at || '').localeCompare(String(left.latest_created_at || ''));
        });
      }

      function tokenizeForSessionRecommendation(value, maxTokens = 48) {
        const text = String(value || '').toLowerCase();
        const tokens = [];
        const seen = new Set();

        for (const match of text.matchAll(/[a-z0-9_+.#-]{2,}|[\u4e00-\u9fff]{2,}/g)) {
          const chunk = match[0] || '';
          const candidates = [];
          if (/^[\u4e00-\u9fff]{2,}$/.test(chunk)) {
            candidates.push(chunk);
            if (chunk.length > 2) {
              for (let index = 0; index < chunk.length - 1; index += 1) {
                candidates.push(chunk.slice(index, index + 2));
              }
            }
          } else {
            candidates.push(chunk);
          }

          for (const candidate of candidates) {
            const normalized = candidate.trim();
            if (normalized.length < 2 || seen.has(normalized)) {
              continue;
            }
            seen.add(normalized);
            tokens.push(normalized);
            if (tokens.length >= maxTokens) {
              return tokens;
            }
          }
        }

        return tokens;
      }

      function pickRecommendedNoteForSession(hit, notes) {
        if (!Array.isArray(notes) || !notes.length) {
          return null;
        }

        const hitText = [
          noteSearchInput.value.trim(),
          hit.preview_title,
          ...(hit.snippets || [])
        ].join(' ');
        const hitTokens = tokenizeForSessionRecommendation(hitText);
        if (!hitTokens.length) {
          return null;
        }

        let best = null;
        for (const note of notes) {
          const noteText = [
            note.title,
            note.problem,
            note.root_cause,
            note.solution,
            note.key_takeaways,
            ...(note.tags || [])
          ].join(' ');
          const noteTokens = new Set(tokenizeForSessionRecommendation(noteText, 80));
          if (!noteTokens.size) {
            continue;
          }

          const sharedTerms = hitTokens.filter((token) => noteTokens.has(token));
          let score = sharedTerms.length;
          const noteTitle = String(note.title || '').trim();
          if (noteTitle && String(hitText).includes(noteTitle)) {
            score += 4;
          }
          score += Math.min((note.tags || []).filter((tag) => hitText.includes(tag)).length * 3, 6);
          if (score <= 0) {
            continue;
          }

          const candidate = {
            id: note.id,
            title: note.title,
            status: note.status,
            status_label: note.status_label,
            updated_at: note.updated_at,
            source_count: note.source_count,
            tags: note.tags || [],
            reason: sharedTerms.length
              ? `共享命中词：${sharedTerms.slice(0, 3).join(' / ')}`
              : '当前搜索结果里最接近的已有笔记',
            score
          };
          if (!best || candidate.score > best.score) {
            best = candidate;
          }
        }

        return best;
      }

      function syncSessionRecommendations() {
        currentSessionHits = currentSessionHits.map((item) => ({
          ...item,
          recommended_note: pickRecommendedNoteForSession(item, currentNotes)
        }));
      }

      function renderSessionResults() {
        const query = noteSearchInput.value.trim();
        if (!query) {
          sessionSearchSection.hidden = true;
          sessionResultCount.textContent = '0 组会话';
          sessionSearchResults.innerHTML = '';
          return;
        }

        sessionSearchSection.hidden = false;
        sessionResultCount.textContent = `${currentSessionHits.length} 组会话`;
        if (!currentSessionHits.length) {
          sessionSearchResults.innerHTML = `
            <section class="empty-state compact">
              <h3>没有命中原始会话</h3>
              <p>当前关键词没有匹配到原始消息，可以先看下面的笔记结果，或者换个说法再试一次。</p>
            </section>
          `;
          return;
        }

        sessionSearchResults.innerHTML = currentSessionHits.map((item) => {
          const snippets = (item.snippets || []).map((snippet) => `
            <article class="session-hit-snippet">
              <p>${highlightText(snippet, query)}</p>
            </article>
          `).join('');
          const roles = (item.roles || []).length ? item.roles.join(' / ') : '原始消息';
          const recommendedNote = item.recommended_note || null;
          const recommendationBlock = recommendedNote
            ? `
              <section class="session-recommendation">
                <div class="compact-inline-head compact-inline-head-narrow">
                  <div>
                    <p class="eyebrow">推荐追加</p>
                    <h4>${escapeHtml(recommendedNote.title || `笔记 ${recommendedNote.id}`)}</h4>
                    <p class="panel-text">${escapeHtml(recommendedNote.reason || '当前搜索结果里最接近的已有笔记')}</p>
                  </div>
                  <button
                    type="button"
                    class="secondary-btn quick-append-search-session"
                    data-source="${escapeHtml(item.source)}"
                    data-session-id="${escapeHtml(item.session_id)}"
                    data-note-id="${escapeHtml(recommendedNote.id)}"
                  >
                    一键追加到这篇
                  </button>
                  <button
                    type="button"
                    class="ghost-button preview-append-search-session"
                    data-source="${escapeHtml(item.source)}"
                    data-session-id="${escapeHtml(item.session_id)}"
                    data-note-id="${escapeHtml(recommendedNote.id)}"
                  >
                    预览追加差异
                  </button>
                </div>
              </section>
            `
            : '';
          const action = item.session_id
            ? `
              <button
                type="button"
                class="secondary-btn quick-save-search-session"
                data-source="${escapeHtml(item.source)}"
                data-session-id="${escapeHtml(item.session_id)}"
              >
                一键存草稿
              </button>
              <a
                class="ghost-button"
                href="/?compose_source=${encodeURIComponent(item.source)}&compose_session_id=${encodeURIComponent(item.session_id)}&compose_title=${encodeURIComponent(item.preview_title || '')}"
              >
                进入整理面板
              </a>
              <button
                type="button"
                class="ghost-button open-session-search-result"
                data-source="${escapeHtml(item.source)}"
                data-session-id="${escapeHtml(item.session_id)}"
                data-title="${escapeHtml(item.preview_title)}"
              >
                查看整段会话
              </button>
            `
            : '';

          return `
            <article class="session-hit-card">
              <header class="browser-head">
                <div>
                  <p class="eyebrow">${escapeHtml(item.source)}</p>
                  <h3>${escapeHtml(item.preview_title)}</h3>
                </div>
                <span class="pill">${escapeHtml(item.match_count)} 条命中</span>
              </header>
              <div class="inline-meta">
                <span>${escapeHtml(roles)}</span>
                <span>${escapeHtml(item.latest_created_at || '')}</span>
              </div>
              <div class="session-hit-snippets">
                ${snippets}
              </div>
              ${recommendationBlock}
              ${action ? `<div class="inline-actions">${action}</div>` : ''}
            </article>
          `;
        }).join('');
      }

      function setAppendPreviewNotice(message, type = '') {
        appendPreviewNotice.textContent = message;
        appendPreviewNotice.className = type ? `notice ${type}` : 'notice';
      }

      function openAppendPreviewShell() {
        appendPreviewShell.hidden = false;
        document.body.classList.add('composer-open');
      }

      function closeAppendPreviewShell() {
        activeAppendPreview = null;
        appendPreviewShell.hidden = true;
        appendPreviewTitle.textContent = '确认这次要追加到哪篇笔记';
        appendPreviewHint.textContent = '先看清楚会新增哪些内容，再决定是否直接并入已有笔记。';
        appendPreviewSummary.innerHTML = '<p class="source-empty">正在准备追加预览...</p>';
        appendPreviewSections.innerHTML = '<p class="source-empty">正在生成差异内容...</p>';
        setAppendPreviewNotice('');
        confirmAppendPreviewBtn.disabled = false;
        confirmAppendPreviewBtn.textContent = '确认追加到这篇';
        document.body.classList.remove('composer-open');
      }

      function renderAppendPreview(preview) {
        const { sessionHit, note, draft, sources, sourceCountAdded, canAppend, blockingReason } = preview;
        const sections = [
          ['问题描述', analyzeAppendSection(note.problem, draft.problem)],
          ['根本原因', analyzeAppendSection(note.root_cause, draft.root_cause)],
          ['解决方案', analyzeAppendSection(note.solution, draft.solution)],
          ['关键收获', analyzeAppendSection(note.key_takeaways, draft.key_takeaways)],
        ];
        const changedCount = sections.filter(([, result]) => result.changed).length;

        appendPreviewTitle.textContent = `将会话补充到《${note.title}》`;
        appendPreviewHint.textContent = `来源：${sessionHit.source} / ${sessionHit.session_id} · 本次会带入 ${sources.length} 条原始消息`;
        appendPreviewSummary.innerHTML = `
          <div class="inline-meta">
            <span>目标笔记：${escapeHtml(note.title)}</span>
            <span>${escapeHtml(note.status_label || note.status || '草稿')}</span>
            <span>当前 ${escapeHtml(note.source_count)} 条来源</span>
            <span>本次新增 ${escapeHtml(sourceCountAdded || 0)} 条来源</span>
            <span>${escapeHtml(changedCount)} 个栏位会发生变化</span>
          </div>
        `;
        appendPreviewSections.innerHTML = sections.map(([label, result]) => `
          <article class="append-preview-card">
            <header class="browser-head">
              <h3>${escapeHtml(label)}</h3>
              <span class="pill">${escapeHtml(result.status)}</span>
            </header>
            <p class="panel-text">${escapeHtml(result.reason)}</p>
            <div class="append-preview-body">
              <section class="append-preview-block">
                <h4>当前笔记</h4>
                <p>${result.existing ? escapeHtml(result.existing) : '这一栏目前还是空的。'}</p>
              </section>
              <section class="append-preview-block">
                <h4>本次新增草稿</h4>
                <p>${result.incoming ? escapeHtml(result.incoming) : '这次没有稳定生成可追加内容。'}</p>
              </section>
            </div>
          </article>
        `).join('');
        confirmAppendPreviewBtn.disabled = !canAppend;
        confirmAppendPreviewBtn.textContent = canAppend ? '确认追加到这篇' : '没有新增可并入内容';
        if (!canAppend) {
          setAppendPreviewNotice(blockingReason || '没有检测到新的来源或新增段落，这次追加已拦截。', 'error');
        }
      }

      async function quickAppendSessionToNote(source, sessionId, noteId) {
        const resp = await fetch('/api/notes/quick-append/session', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source,
            session_id: sessionId,
            note_id: Number(noteId)
          })
        });
        if (!resp.ok) {
          const data = await resp.json().catch(() => ({}));
          throw new Error(data?.detail || `追加失败: ${resp.status}`);
        }
        return resp.json();
      }

      async function openAppendPreview(source, sessionId, noteId) {
        const note = noteStore.get(Number(noteId)) || currentNotes.find((item) => Number(item.id) === Number(noteId));
        const sessionHit = currentSessionHits.find(
          (item) => item.source === source && item.session_id === sessionId
        );
        if (!note || !sessionHit) {
          window.alert('暂时无法生成追加预览，请先重新搜索一次。');
          return;
        }

        openAppendPreviewShell();
        setAppendPreviewNotice('正在生成追加差异预览...');

        try {
          const [draftResp, noteSourcesResp] = await Promise.all([
            fetch('/api/notes/generate/session', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ source, session_id: sessionId })
            }),
            fetch(`/api/notes/${noteId}/sources`)
          ]);
          if (!draftResp.ok) {
            throw new Error(`预览生成失败: ${draftResp.status}`);
          }
          if (!noteSourcesResp.ok) {
            throw new Error(`无法比较已有来源: ${noteSourcesResp.status}`);
          }

          const data = await draftResp.json();
          const noteSourcesData = await noteSourcesResp.json();
          const existingSourceIds = new Set((noteSourcesData.items || []).map((item) => Number(item.id)));
          const sourceCountAdded = (data.sources || []).filter((item) => !existingSourceIds.has(Number(item.id))).length;
          const previewSections = [
            analyzeAppendSection(note.problem, data.draft?.problem),
            analyzeAppendSection(note.root_cause, data.draft?.root_cause),
            analyzeAppendSection(note.solution, data.draft?.solution),
            analyzeAppendSection(note.key_takeaways, data.draft?.key_takeaways),
          ];
          const changedCount = previewSections.filter((result) => result.changed).length;
          const canAppend = Boolean(sourceCountAdded > 0 || changedCount > 0);
          activeAppendPreview = {
            source,
            sessionId,
            noteId: Number(noteId),
            note,
            sessionHit,
            draft: data.draft || {},
            sources: data.sources || [],
            sourceCountAdded,
            canAppend,
            blockingReason: canAppend ? '' : '没有检测到新的来源或新增段落，这次追加已拦截。'
          };
          renderAppendPreview(activeAppendPreview);
          if (canAppend) {
            setAppendPreviewNotice('确认无误后，可以直接把这些补充并入目标笔记。', 'success');
          }
        } catch (error) {
          activeAppendPreview = null;
          appendPreviewSummary.innerHTML = '<p class="source-empty">未能准备好本次追加预览。</p>';
          appendPreviewSections.innerHTML = '<p class="source-empty">请稍后再试，或者直接进入整理面板手动确认。</p>';
          confirmAppendPreviewBtn.disabled = true;
          confirmAppendPreviewBtn.textContent = '没有新增可并入内容';
          setAppendPreviewNotice(error.message || '生成预览失败，请稍后再试。', 'error');
        }
      }

      function availableStackTags(notes) {
        const tags = new Set();
        for (const note of notes) {
          for (const tag of note.stack_tags || []) {
            if (tag) {
              tags.add(tag);
            }
          }
        }
        if (activeStackFilter !== 'all') {
          tags.add(activeStackFilter);
        }
        return [...tags].sort((left, right) => left.localeCompare(right, 'zh-CN'));
      }

      function availableNoteTags(notes) {
        const tags = new Set();
        for (const note of notes) {
          for (const tag of note.tags || []) {
            if (tag) {
              tags.add(tag);
            }
          }
        }
        if (activeNoteTagFilter !== 'all') {
          tags.add(activeNoteTagFilter);
        }
        return [...tags].sort((left, right) => left.localeCompare(right, 'zh-CN'));
      }

      function filterNotesByStack(notes) {
        if (activeStackFilter === 'all') {
          return notes;
        }
        return notes.filter((note) => (note.stack_tags || []).includes(activeStackFilter));
      }

      function filterNotesByTag(notes) {
        if (activeNoteTagFilter === 'all') {
          return notes;
        }
        return notes.filter((note) => (note.tags || []).includes(activeNoteTagFilter));
      }

      function filterNotesByStatus(notes) {
        if (activeStatusFilter === 'all') {
          return notes;
        }
        return notes.filter((note) => String(note.status || '') === activeStatusFilter);
      }

      function renderStackFilters(notes) {
        const items = ['all', ...availableStackTags(notes)];
        stackFilterList.innerHTML = items.map((tag) => {
          const isActive = tag === activeStackFilter;
          const label = tag === 'all' ? '全部' : tag;
          return `
            <button
              type="button"
              class="tag-filter-btn${isActive ? ' is-active' : ''}"
              data-stack-filter="${escapeHtml(tag)}"
            >
              ${escapeHtml(label)}
            </button>
          `;
        }).join('');
      }

      function renderNoteTagFilters(notes) {
        const items = ['all', ...availableNoteTags(notes)];
        noteTagFilterList.innerHTML = items.map((tag) => {
          const isActive = tag === activeNoteTagFilter;
          const label = tag === 'all' ? '全部' : tag;
          return `
            <button
              type="button"
              class="tag-filter-btn${isActive ? ' is-active' : ''}"
              data-note-tag-filter="${escapeHtml(tag)}"
            >
              ${escapeHtml(label)}
            </button>
          `;
        }).join('');
      }

      function renderStatusFilters(notes) {
        const items = ['all', 'draft', 'reviewed', 'published'];
        statusFilterList.innerHTML = items.map((status) => {
          const count = status === 'all'
            ? notes.length
            : notes.filter((note) => String(note.status || '') === status).length;
          const isActive = status === activeStatusFilter;
          return `
            <button
              type="button"
              class="tag-filter-btn${isActive ? ' is-active' : ''}"
              data-status-filter="${escapeHtml(status)}"
            >
              ${escapeHtml(noteStatusLabel(status))} · ${count}
            </button>
          `;
        }).join('');
      }

      function renderNoteCard(note) {
        const searchQuery = noteSearchInput.value.trim();
        const sourceLabels = (note.source_labels || []).join(' / ') || '未标记来源';
        const noteTags = (note.tags || [])
          .map((tag) => `<span class="mini-tag note-tag">${escapeHtml(tag)}</span>`)
          .join('');
        const stackTags = (note.stack_tags || [])
          .map((tag) => `<span class="mini-tag stack-tag">${escapeHtml(tag)}</span>`)
          .join('');
        const isSelected = selectedNoteIds.includes(Number(note.id));
        return `
          <article class="note-card${isSelected ? ' is-selected' : ''}">
            <header class="note-card-header">
              <div>
                <h2>${highlightText(note.title, searchQuery)}</h2>
                <div class="inline-meta">
                  <span>创建于 ${escapeHtml(note.created_at)}</span>
                  <span>更新于 ${escapeHtml(note.updated_at)}</span>
                  <span>${escapeHtml(note.source_count)} 条来源</span>
                  <span>${escapeHtml(sourceLabels)}</span>
                </div>
                ${noteTags ? `<div class="note-tag-row">${noteTags}</div>` : ''}
                ${stackTags ? `<div class="stack-tag-row">${stackTags}</div>` : ''}
              </div>
              <div class="inline-actions">
                <label class="inline-meta inline-meta-tight">
                  <input
                    type="checkbox"
                    class="note-select-toggle"
                    data-note-id="${note.id}"
                    ${isSelected ? 'checked' : ''}
                  />
                  <span>选择</span>
                </label>
                <span class="pill">${escapeHtml(note.status_label || noteStatusLabel(note.status))}</span>
              </div>
            </header>

            <section class="note-section">
              <h3>问题描述</h3>
              <p>${highlightText(note.problem, searchQuery)}</p>
            </section>

            <section class="note-section">
              <h3>根本原因</h3>
              <p>${highlightText(note.root_cause, searchQuery)}</p>
            </section>

            <section class="note-section">
              <h3>解决方案</h3>
              <p>${highlightText(note.solution, searchQuery)}</p>
            </section>

            <section class="note-section">
              <h3>关键收获</h3>
              <p>${highlightText(note.key_takeaways, searchQuery)}</p>
            </section>

            <footer class="browser-foot note-card-foot">
              <span>${escapeHtml(note.source_type || 'mixed')}</span>
              <div class="inline-actions">
                <button type="button" class="ghost-button open-edit-note" data-note-id="${note.id}">
                  编辑笔记
                </button>
                <button type="button" class="ghost-button export-note-markdown" data-note-id="${note.id}">
                  导出 Markdown
                </button>
                <button type="button" class="danger-button open-delete-note" data-note-id="${note.id}">
                  删除笔记
                </button>
                <button type="button" class="ghost-button open-note-sources" data-note-id="${note.id}" data-note-title="${escapeHtml(note.title)}">
                  查看来源对话
                </button>
              </div>
            </footer>
          </article>
        `;
      }

      function renderNotes(notes) {
        if (noteSearchInput.value.trim() && currentSessionHits.length) {
          syncSessionRecommendations();
          renderSessionResults();
        }
        renderStackFilters(notes);
        renderNoteTagFilters(notes);
        renderStatusFilters(notes);
        const visibleNotes = filterNotesByStatus(filterNotesByTag(filterNotesByStack(notes)));
        pruneSelectedNotes(visibleNotes);
        renderNoteBatchBar();
        persistNotesPreferences();
        const activeLabels = [];
        if (activeStatusFilter !== 'all') {
          activeLabels.push(noteStatusLabel(activeStatusFilter));
        }
        if (activeStackFilter !== 'all') {
          activeLabels.push(activeStackFilter);
        }
        if (activeNoteTagFilter !== 'all') {
          activeLabels.push(`#${activeNoteTagFilter}`);
        }
        noteCount.textContent = activeLabels.length
          ? `${visibleNotes.length} 篇 · ${activeLabels.join(' / ')}`
          : `${visibleNotes.length} 篇笔记`;
        if (!visibleNotes.length) {
          const filterHints = [];
          if (activeStatusFilter !== 'all') {
            filterHints.push(noteStatusLabel(activeStatusFilter));
          }
          if (activeStackFilter !== 'all') {
            filterHints.push(activeStackFilter);
          }
          if (activeNoteTagFilter !== 'all') {
            filterHints.push(`#${activeNoteTagFilter}`);
          }
          noteResultsEl.innerHTML = `
            <section class="empty-state">
              <h2>没有找到匹配笔记</h2>
              <p>${filterHints.length
                ? `当前筛选为 ${escapeHtml(filterHints.join(' / '))}，可以切换到“全部”或换个关键词。`
                : '换一个关键词试试，或者点击“重置”查看全部笔记。'}</p>
            </section>
          `;
          return;
        }

        noteResultsEl.innerHTML = visibleNotes.map(renderNoteCard).join('');
      }

      function openSourcesModal(title) {
        sourceModalTitle.textContent = title || '查看来源消息';
        sourceModalHint.textContent = '这里展示这篇笔记关联的原始消息。';
        sourceModalList.innerHTML = '<p class="source-empty">正在加载来源消息...</p>';
        sourceShell.hidden = false;
        document.body.classList.add('composer-open');
      }

      function closeSourcesModal() {
        sourceShell.hidden = true;
        document.body.classList.remove('composer-open');
      }

      function openSessionModal(title) {
        sessionModalTitle.textContent = title || '查看完整会话';
        sessionModalHint.textContent = '这里展示搜索命中的完整原始会话。';
        sessionModalList.innerHTML = '<p class="source-empty">正在加载完整会话...</p>';
        sessionShell.hidden = false;
        document.body.classList.add('composer-open');
      }

      function closeSessionModal() {
        sessionShell.hidden = true;
        document.body.classList.remove('composer-open');
      }

      function setEditNotice(message, type = '') {
        editNotice.textContent = message;
        editNotice.className = type ? `notice ${type}` : 'notice';
      }

      function openEditModal(noteId) {
        const note = noteStore.get(noteId);
        if (!note) return;

        activeEditNoteId = noteId;
        editModalTitle.textContent = `编辑：${note.title}`;
        renderAppendSummaryCard(takeAppendSummary(noteId));
        loadAppendHistory(noteId);
        const restoredDraft = loadEditDraft(noteId);
        if (restoredDraft) {
          editTitle.value = restoredDraft.title || '';
          editStatus.value = restoredDraft.status || 'draft';
          editTags.value = restoredDraft.tags || '';
          editProblem.value = restoredDraft.problem || '';
          editRootCause.value = restoredDraft.root_cause || '';
          editSolution.value = restoredDraft.solution || '';
          editTakeaways.value = restoredDraft.key_takeaways || '';
          setEditNotice('已恢复本地未保存修改。', 'success');
        } else {
          fillEditForm(note);
          setEditNotice('');
        }
        editShell.hidden = false;
        document.body.classList.add('composer-open');
      }

      function openRequestedNoteIfNeeded() {
        if (!requestedNoteId || !noteStore.has(requestedNoteId)) {
          return;
        }

        openEditModal(requestedNoteId);
        const note = noteStore.get(requestedNoteId);
        if (note?.status === 'draft' && editAppendSummaryCard.hidden && !editNotice.textContent) {
          setEditNotice('这是刚存下来的草稿，先把标题和关键收获修顺就够了。');
        }
      }

      function closeEditModal() {
        activeEditNoteId = null;
        editNoteForm.reset();
        hideAppendSummaryCard();
        hideAppendTimelineCard();
        setEditNotice('');
        editShell.hidden = true;
        document.body.classList.remove('composer-open');
      }

      function upsertNote(note) {
        noteStore.set(note.id, note);
        const initialIndex = initialNotes.findIndex((item) => item.id === note.id);
        if (initialIndex !== -1) {
          initialNotes.splice(initialIndex, 1, note);
        }

        const currentIndex = currentNotes.findIndex((item) => item.id === note.id);
        if (currentIndex !== -1) {
          currentNotes.splice(currentIndex, 1, note);
        }
      }

      function removeNoteLocally(noteId) {
        noteStore.delete(noteId);

        const initialIndex = initialNotes.findIndex((item) => item.id === noteId);
        if (initialIndex !== -1) {
          initialNotes.splice(initialIndex, 1);
        }

        const currentIndex = currentNotes.findIndex((item) => item.id === noteId);
        if (currentIndex !== -1) {
          currentNotes.splice(currentIndex, 1);
        }
      }

      async function searchNotes() {
        const q = noteSearchInput.value.trim();
        if (!q) {
          currentNotes = [...initialNotes];
          currentSessionHits = [];
          renderSessionResults();
          renderNotes(currentNotes);
          return;
        }

        const [noteResp, rawResp] = await Promise.all([
          fetch('/api/notes/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ q, limit: 50 })
          }),
          fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ q, limit: 30 })
          })
        ]);

        if (!noteResp.ok) {
          throw new Error(`笔记搜索失败: ${noteResp.status}`);
        }
        if (!rawResp.ok) {
          throw new Error(`原始会话搜索失败: ${rawResp.status}`);
        }

        const noteData = await noteResp.json();
        const rawData = await rawResp.json();
        currentNotes = noteData.items || [];
        for (const note of currentNotes) {
          noteStore.set(note.id, note);
        }
        currentSessionHits = groupSessionHits(rawData.items || []);
        syncSessionRecommendations();
        renderSessionResults();
        renderNotes(currentNotes);
      }

      async function loadSources(noteId, title) {
        openSourcesModal(title);

        try {
          const resp = await fetch(`/api/notes/${noteId}/sources`);
          if (!resp.ok) {
            throw new Error(`加载失败: ${resp.status}`);
          }

          const data = await resp.json();
          const items = data.items || [];
          sourceModalHint.textContent = `共关联 ${items.length} 条原始消息。`;

          if (!items.length) {
            sourceModalList.innerHTML = '<p class="source-empty">这篇笔记暂时没有关联到来源消息。</p>';
            return;
          }

          sourceModalList.innerHTML = items.map((item) => `
            <article class="source-item source-item-large">
              <header>
                <div class="inline-meta inline-meta-tight">
                  <span class="source-badge">${escapeHtml(item.role)}</span>
                  <span>${escapeHtml(item.source)}${item.session_id ? ` / ${escapeHtml(item.session_id)}` : ''}</span>
                </div>
                <span>${escapeHtml(item.created_at)}</span>
              </header>
              <p>${escapeHtml(item.content)}</p>
            </article>
          `).join('');
        } catch (error) {
          sourceModalHint.textContent = error.message || '加载来源消息失败，请稍后再试。';
          sourceModalList.innerHTML = '<p class="source-empty">未能加载来源消息。</p>';
        }
      }

      async function loadSessionResult(source, sessionId, title) {
        openSessionModal(title);

        try {
          const resp = await fetch(
            `/api/sessions/messages?source=${encodeURIComponent(source)}&session_id=${encodeURIComponent(sessionId)}`
          );
          if (!resp.ok) {
            throw new Error(`加载失败: ${resp.status}`);
          }

          const data = await resp.json();
          const items = data.items || [];
          sessionModalHint.textContent = `来源：${source} · 共 ${items.length} 条原始消息`;

          if (!items.length) {
            sessionModalList.innerHTML = '<p class="source-empty">这段会话暂时没有可展示的原始消息。</p>';
            return;
          }

          const query = noteSearchInput.value.trim();
          sessionModalList.innerHTML = items.map((item) => `
            <article class="transcript-item transcript-role-${escapeHtml(item.role || 'unknown')}">
              <header class="transcript-meta">
                <div class="inline-meta inline-meta-tight">
                  <span class="source-badge">${escapeHtml(item.role)}</span>
                  <span>${escapeHtml(item.source)}${item.session_id ? ` / ${escapeHtml(item.session_id)}` : ''}</span>
                </div>
                <span>${escapeHtml(item.created_at)}</span>
              </header>
              <div class="transcript-text">${highlightText(item.content, query)}</div>
            </article>
          `).join('');
        } catch (error) {
          sessionModalHint.textContent = error.message || '加载原始会话失败，请稍后再试。';
          sessionModalList.innerHTML = '<p class="source-empty">未能加载完整会话。</p>';
        }
      }

      async function saveNoteEdit(event) {
        event.preventDefault();
        if (!activeEditNoteId) return;

        saveEditBtn.disabled = true;
        setEditNotice('正在保存修改...');

        try {
          const resp = await fetch(`/api/notes/${activeEditNoteId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title: editTitle.value.trim(),
              tags: parseTagInput(editTags.value),
              problem: editProblem.value.trim(),
              root_cause: editRootCause.value.trim(),
              solution: editSolution.value.trim(),
              key_takeaways: editTakeaways.value.trim(),
              status: editStatus.value,
              source_type: noteStore.get(activeEditNoteId)?.source_type || 'mixed'
            })
          });

          if (!resp.ok) {
            throw new Error(`保存失败: ${resp.status}`);
          }

          const data = await resp.json();
          clearEditDraft(activeEditNoteId);
          upsertNote(data.note);
          renderNotes(currentNotes);
          setEditNotice('修改已保存。', 'success');
          window.setTimeout(closeEditModal, 350);
        } catch (error) {
          setEditNotice(error.message || '保存修改失败，请稍后再试。', 'error');
        } finally {
          saveEditBtn.disabled = false;
        }
      }

      async function deleteNote(noteId) {
        const note = noteStore.get(noteId);
        if (!note) return;

        const confirmed = window.confirm(`确定删除笔记《${note.title}》吗？此操作不可撤销。`);
        if (!confirmed) return;

        try {
          const resp = await fetch(`/api/notes/${noteId}`, {
            method: 'DELETE'
          });
          if (!resp.ok) {
            throw new Error(`删除失败: ${resp.status}`);
          }

          clearEditDraft(noteId);
          removeNoteLocally(noteId);
          renderNotes(currentNotes);
          if (activeEditNoteId === noteId) {
            closeEditModal();
          }
        } catch (error) {
          if (activeEditNoteId === noteId) {
            setEditNotice(error.message || '删除失败，请稍后再试。', 'error');
          } else {
            window.alert(error.message || '删除失败，请稍后再试。');
          }
        }
      }

      document.getElementById('noteSearchBtn').addEventListener('click', searchNotes);
      document.getElementById('noteResetBtn').addEventListener('click', () => {
        noteSearchInput.value = '';
        activeStackFilter = 'all';
        activeNoteTagFilter = 'all';
        activeStatusFilter = 'all';
        currentNotes = [...initialNotes];
        currentSessionHits = [];
        clearNoteSelection();
        renderSessionResults();
        renderNotes(currentNotes);
      });
      noteSearchInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
          searchNotes();
        }
      });

      noteResultsEl.addEventListener('click', (event) => {
        const selectionTrigger = event.target.closest('.note-select-toggle');
        if (selectionTrigger) {
          toggleNoteSelection(Number(selectionTrigger.dataset.noteId));
          renderNotes(currentNotes);
          return;
        }

        const editTrigger = event.target.closest('.open-edit-note');
        if (editTrigger) {
          openEditModal(Number(editTrigger.dataset.noteId));
          return;
        }

        const exportTrigger = event.target.closest('.export-note-markdown');
        if (exportTrigger) {
          downloadNoteMarkdown(Number(exportTrigger.dataset.noteId));
          return;
        }

        const deleteTrigger = event.target.closest('.open-delete-note');
        if (deleteTrigger) {
          deleteNote(Number(deleteTrigger.dataset.noteId));
          return;
        }

        const trigger = event.target.closest('.open-note-sources');
        if (!trigger) return;
        loadSources(trigger.dataset.noteId, trigger.dataset.noteTitle);
      });
      editAppendTimelineFilters.addEventListener('click', (event) => {
        const trigger = event.target.closest('[data-append-timeline-filter]');
        if (!trigger) return;
        activeAppendTimelineFilter = String(trigger.dataset.appendTimelineFilter || 'all');
        renderAppendTimeline(activeAppendTimelineEvents);
      });
      editAppendTimelineSearchInput.addEventListener('input', (event) => {
        activeAppendTimelineQuery = String(event.target.value || '').trim();
        renderAppendTimeline(activeAppendTimelineEvents);
      });
      editAppendTimelineSearchResetBtn.addEventListener('click', () => {
        editAppendTimelineSearchInput.value = '';
        activeAppendTimelineQuery = '';
        renderAppendTimeline(activeAppendTimelineEvents);
      });
      editAppendTimelineList.addEventListener('click', (event) => {
        const undoTrigger = event.target.closest('.undo-append-history-event');
        if (undoTrigger) {
          const eventId = Number(undoTrigger.dataset.appendEventId || 0);
          if (!eventId || !activeEditNoteId) {
            return;
          }
          if (
            hasEditChanges() &&
            !window.confirm('当前笔记有未保存修改，撤销追加会覆盖这些改动。确定继续吗？')
          ) {
            return;
          }
          if (!window.confirm('确定撤销最近一次追加吗？这会移除那次并入的来源和新增内容。')) {
            return;
          }

          undoTrigger.disabled = true;
          undoTrigger.textContent = '正在撤销...';
          fetch(`/api/notes/${activeEditNoteId}/history/${eventId}/undo`, {
            method: 'POST'
          })
            .then(async (resp) => {
              if (!resp.ok) {
                const data = await resp.json().catch(() => ({}));
                throw new Error(data?.detail || `撤销失败: ${resp.status}`);
              }
              return resp.json();
            })
            .then((data) => {
              if (!data?.note) {
                throw new Error('撤销后未返回最新笔记内容。');
              }
              clearEditDraft(activeEditNoteId);
              upsertNote(data.note);
              fillEditForm(data.note);
              hideAppendSummaryCard();
              activeAppendTimelineEventId = null;
              activeAppendTimelineExpandedIds = new Set();
              renderAppendTimeline(data.history || []);
              renderNotes(currentNotes);
              setEditNotice('最近一次追加已撤销。', 'success');
            })
            .catch((error) => {
              setEditNotice(error.message || '撤销追加失败，请稍后再试。', 'error');
            });
          return;
        }
        const toggleTrigger = event.target.closest('.toggle-append-history-event');
        if (toggleTrigger) {
          const eventId = Number(toggleTrigger.dataset.appendEventId || 0);
          if (activeAppendTimelineExpandedIds.has(eventId)) {
            activeAppendTimelineExpandedIds.delete(eventId);
          } else {
            activeAppendTimelineExpandedIds.add(eventId);
          }
          renderAppendTimeline(activeAppendTimelineEvents);
          return;
        }
        const focusTrigger = event.target.closest('.focus-append-history-event');
        if (focusTrigger) {
          focusAppendTimelineEvent(focusTrigger.dataset.appendEventId);
          return;
        }
        const trigger = event.target.closest('.open-append-history-session');
        if (!trigger) return;
        loadSessionResult(trigger.dataset.source, trigger.dataset.sessionId, trigger.dataset.title);
      });
      sessionSearchResults.addEventListener('click', (event) => {
        const previewAppendTrigger = event.target.closest('.preview-append-search-session');
        if (previewAppendTrigger) {
          openAppendPreview(
            previewAppendTrigger.dataset.source,
            previewAppendTrigger.dataset.sessionId,
            previewAppendTrigger.dataset.noteId
          );
          return;
        }

        const quickAppendTrigger = event.target.closest('.quick-append-search-session');
        if (quickAppendTrigger) {
          quickAppendTrigger.disabled = true;
          quickAppendTrigger.textContent = '正在追加...';
          quickAppendSessionToNote(
            quickAppendTrigger.dataset.source,
            quickAppendTrigger.dataset.sessionId,
            quickAppendTrigger.dataset.noteId
          )
            .then((data) => {
              const noteId = Number(data?.note?.id || 0);
              persistAppendSummary(noteId, data?.append_summary || null);
              window.location.href = noteId
                ? `/notes?note_id=${encodeURIComponent(noteId)}`
                : '/notes';
            })
            .catch((error) => {
              quickAppendTrigger.disabled = false;
              quickAppendTrigger.textContent = '一键追加到这篇';
              window.alert(error.message || '快速追加失败，请稍后再试。');
            });
          return;
        }

        const quickSaveTrigger = event.target.closest('.quick-save-search-session');
        if (quickSaveTrigger) {
          quickSaveTrigger.disabled = true;
          quickSaveTrigger.textContent = '正在存草稿...';
          fetch('/api/notes/quick-save/session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              source: quickSaveTrigger.dataset.source,
              session_id: quickSaveTrigger.dataset.sessionId
            })
          })
            .then(async (resp) => {
              if (!resp.ok) {
                throw new Error(`保存失败: ${resp.status}`);
              }
              return resp.json();
            })
            .then((data) => {
              const noteId = Number(data?.note?.id || 0);
              window.location.href = noteId
                ? `/notes?note_id=${encodeURIComponent(noteId)}`
                : '/notes';
            })
            .catch((error) => {
              quickSaveTrigger.disabled = false;
              quickSaveTrigger.textContent = '一键存草稿';
              window.alert(error.message || '快速保存失败，请稍后再试。');
            });
          return;
        }

        const trigger = event.target.closest('.open-session-search-result');
        if (!trigger) return;
        loadSessionResult(trigger.dataset.source, trigger.dataset.sessionId, trigger.dataset.title);
      });

      stackFilterList.addEventListener('click', (event) => {
        const trigger = event.target.closest('[data-stack-filter]');
        if (!trigger) return;
        activeStackFilter = trigger.dataset.stackFilter || 'all';
        renderNotes(currentNotes);
      });
      noteTagFilterList.addEventListener('click', (event) => {
        const trigger = event.target.closest('[data-note-tag-filter]');
        if (!trigger) return;
        activeNoteTagFilter = normalizeNoteTagFilter(trigger.dataset.noteTagFilter || 'all');
        renderNotes(currentNotes);
      });
      statusFilterList.addEventListener('click', (event) => {
        const trigger = event.target.closest('[data-status-filter]');
        if (!trigger) return;
        activeStatusFilter = normalizeStatusFilter(trigger.dataset.statusFilter || 'all');
        renderNotes(currentNotes);
      });

      document.getElementById('closeEditBtn').addEventListener('click', requestCloseEditModal);
      document.querySelector('[data-close-edit]').addEventListener('click', requestCloseEditModal);
      clearNoteSelectionBtn.addEventListener('click', () => {
        clearNoteSelection();
        renderNotes(currentNotes);
      });
      batchExportNotesBtn.addEventListener('click', async () => {
        if (!selectedNoteIds.length) return;
        batchExportNotesBtn.disabled = true;
        batchExportNotesBtn.textContent = '正在打包...';
        try {
          await downloadNotesMarkdownZip(selectedNoteIds);
        } catch (error) {
          window.alert(error.message || '批量导出失败，请稍后再试。');
        } finally {
          batchExportNotesBtn.disabled = false;
          batchExportNotesBtn.textContent = '批量导出 Markdown';
          renderNoteBatchBar();
        }
      });
      editNoteForm.addEventListener('submit', saveNoteEdit);
      editNoteForm.addEventListener('input', persistEditDraft);
      editNoteForm.addEventListener('change', persistEditDraft);
      exportEditBtn.addEventListener('click', () => {
        if (!activeEditNoteId) return;
        downloadNoteMarkdown(activeEditNoteId);
      });
      deleteEditBtn.addEventListener('click', () => {
        if (!activeEditNoteId) return;
        deleteNote(activeEditNoteId);
      });
      document.getElementById('closeSourcesBtn').addEventListener('click', closeSourcesModal);
      document.querySelector('[data-close-sources]').addEventListener('click', closeSourcesModal);
      document.getElementById('closeSessionsBtn').addEventListener('click', closeSessionModal);
      document.querySelector('[data-close-sessions]').addEventListener('click', closeSessionModal);
      document.getElementById('closeAppendPreviewBtn').addEventListener('click', closeAppendPreviewShell);
      document.querySelector('[data-close-append-preview]').addEventListener('click', closeAppendPreviewShell);
      confirmAppendPreviewBtn.addEventListener('click', async () => {
        if (!activeAppendPreview) {
          return;
        }

        confirmAppendPreviewBtn.disabled = true;
        confirmAppendPreviewBtn.textContent = '正在追加...';
        setAppendPreviewNotice('正在把补充内容并入目标笔记...');
        try {
          const data = await quickAppendSessionToNote(
            activeAppendPreview.source,
            activeAppendPreview.sessionId,
            activeAppendPreview.noteId
          );
          const noteId = Number(data?.note?.id || 0);
          persistAppendSummary(noteId, data?.append_summary || null);
          setAppendPreviewNotice('追加完成，正在打开目标笔记。', 'success');
          window.setTimeout(() => {
            window.location.href = noteId
              ? `/notes?note_id=${encodeURIComponent(noteId)}`
              : '/notes';
          }, 220);
        } catch (error) {
          confirmAppendPreviewBtn.disabled = false;
          confirmAppendPreviewBtn.textContent = '确认追加到这篇';
          setAppendPreviewNotice(error.message || '快速追加失败，请稍后再试。', 'error');
        }
      });

      loadNotesPreferences();
      if (noteSearchInput.value.trim()) {
        searchNotes().catch(() => {
          currentNotes = [...initialNotes];
          currentSessionHits = [];
          renderSessionResults();
          renderNotes(currentNotes);
        });
      } else {
        renderSessionResults();
        renderNotes(currentNotes);
      }
      openRequestedNoteIfNeeded();
      window.addEventListener('beforeunload', (event) => {
        if (!shouldWarnBeforeClosingEdit()) {
          return;
        }
        event.preventDefault();
        event.returnValue = '';
      });
})();
