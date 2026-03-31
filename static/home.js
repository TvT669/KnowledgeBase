(() => {
  const bootEl = document.getElementById("homePageBootstrap");
  if (!bootEl) {
    return;
  }

  let boot = {};
  try {
    boot = JSON.parse(bootEl.textContent || "{}");
  } catch (error) {
    console.error("Failed to parse home page bootstrap data.", error);
    return;
  }

  const queryParams = new URLSearchParams(window.location.search);
  const initialInboxGroups = boot.inbox_groups || {};
  const initialInboxStats = boot.inbox_stats || {};
  const initialNoteOptions = Array.isArray(boot.note_options) ? boot.note_options : [];
  const initialSyncState = boot.sync_state || {};
  const initialSyncOptions = initialSyncState.last_options || { include_vscode: true, include_windsurf: true };
      const state = {
        inboxGroups: cloneGroups(initialInboxGroups),
        inboxStats: { ...initialInboxStats },
        noteOptions: [...initialNoteOptions],
        syncState: { ...initialSyncState },
        syncOptions: {
          include_vscode: initialSyncOptions.include_vscode !== false,
          include_windsurf: initialSyncOptions.include_windsurf !== false,
        },
        activeWorkspaceFilter: 'all',
        showIgnored: false,
        workspaceQuery: '',
        selectedSessionKeys: [],
        activeRecordSession: null,
        activeRecordMessages: [],
        activeRecordFilteredMessages: [],
        recordSearch: '',
        recordRole: 'all',
        recordKeyOnly: false,
        activeDraftMode: null,
        activeDraftPayload: null,
        activeMessageIds: [],
        activeSources: [],
        activeRecommendations: [],
        activeConfirmSession: null,
        batchConfirmOpen: false
      };

      const sectionMeta = {
        ready: {
          title: '建议先整理',
          hint: '已经出现问题、方案或结论，适合优先沉淀。'
        },
        new: {
          title: '待判断',
          hint: '系统给出了初步建议，但还值得你再看一眼。'
        },
        later: {
          title: '稍后处理',
          hint: '明确延后，不让首页一直堆积未决会话。'
        },
        done: {
          title: '最近完成',
          hint: '已经整理过的会话，方便你快速回看。'
        },
        ignored: {
          title: '已忽略',
          hint: '这些会话默认不会出现在收件箱里，只有在你主动展开时才会显示。'
        }
      };

      const workspaceFilterMeta = {
        all: {
          label: '全部',
          hint: '优先处理“建议先整理”；想先留住价值时，直接一键存成草稿，再回头慢慢精修。'
        },
        ready: {
          label: '建议先整理',
          hint: '只看已经出现问题、方案或结论的会话，适合优先沉淀。'
        },
        new: {
          label: '待判断',
          hint: '只看还需要你快速判断去留的会话。'
        },
        later: {
          label: '稍后处理',
          hint: '只看暂时延后的会话，适合集中回收旧待办。'
        },
        done: {
          label: '最近完成',
          hint: '只看已经沉淀成笔记的会话，方便回看刚完成的整理结果。'
        },
        ignored: {
          label: '已忽略',
          hint: '只看已经明确忽略的会话，适合集中回收误判或临时跳过的内容。'
        }
      };

      const focusListEl = document.getElementById('focusList');
      const focusCountEl = document.getElementById('focusCount');
      const browserResultsEl = document.getElementById('browserResults');
      const workspaceHintEl = document.getElementById('workspaceHint');
      const workspaceCountEl = document.getElementById('workspaceCount');
      const workspaceFilterListEl = document.getElementById('workspaceFilterList');
      const toggleIgnoredBtn = document.getElementById('toggleIgnoredBtn');
      const batchActionBar = document.getElementById('batchActionBar');
      const batchSelectionTitle = document.getElementById('batchSelectionTitle');
      const clearBatchSelectionBtn = document.getElementById('clearBatchSelectionBtn');
      const batchQuickSaveBtn = document.getElementById('batchQuickSaveBtn');
      const batchConfirmBtn = document.getElementById('batchConfirmBtn');
      const batchReadyBtn = document.getElementById('batchReadyBtn');
      const batchLaterBtn = document.getElementById('batchLaterBtn');
      const batchIgnoreBtn = document.getElementById('batchIgnoreBtn');
      const searchInputEl = document.getElementById('searchInput');
      const pendingMetricEl = document.getElementById('pendingMetric');
      const readyMetricEl = document.getElementById('readyMetric');
      const doneMetricEl = document.getElementById('doneMetric');
      const refreshInboxBtn = document.getElementById('refreshInboxBtn');
      const syncIdeBtn = document.getElementById('syncIdeBtn');
      const autoSyncToggleBtn = document.getElementById('autoSyncToggleBtn');
      const syncSourceList = document.getElementById('syncSourceList');
      const syncStatusText = document.getElementById('syncStatusText');
      const syncMetaLine = document.getElementById('syncMetaLine');
      const confirmShell = document.getElementById('confirmShell');
      const confirmForm = document.getElementById('confirmForm');
      const confirmSessionLabel = document.getElementById('confirmSessionLabel');
      const confirmTitle = document.getElementById('confirmTitle');
      const confirmTags = document.getElementById('confirmTags');
      const confirmPriority = document.getElementById('confirmPriority');
      const confirmNotice = document.getElementById('confirmNotice');
      const batchConfirmShell = document.getElementById('batchConfirmShell');
      const batchConfirmForm = document.getElementById('batchConfirmForm');
      const batchConfirmLabel = document.getElementById('batchConfirmLabel');
      const batchConfirmPriority = document.getElementById('batchConfirmPriority');
      const batchConfirmTags = document.getElementById('batchConfirmTags');
      const batchConfirmNotice = document.getElementById('batchConfirmNotice');
      const composerShell = document.getElementById('composerShell');
      const recordShell = document.getElementById('recordShell');
      const recordTitle = document.getElementById('recordTitle');
      const recordMeta = document.getElementById('recordMeta');
      const recordList = document.getElementById('recordList');
      const recordComposeFilteredBtn = document.getElementById('recordComposeFilteredBtn');
      const recordComposeBtn = document.getElementById('recordComposeBtn');
      const recordSearchInput = document.getElementById('recordSearchInput');
      const recordSearchResetBtn = document.getElementById('recordSearchResetBtn');
      const recordKeyToggleBtn = document.getElementById('recordKeyToggleBtn');
      const composerModePill = document.getElementById('composerModePill');
      const composerSourceCount = document.getElementById('composerSourceCount');
      const composerSourceMeta = document.getElementById('composerSourceMeta');
      const sourcePreviewList = document.getElementById('sourcePreviewList');
      const noteRecommendationCount = document.getElementById('noteRecommendationCount');
      const noteRecommendationList = document.getElementById('noteRecommendationList');
      const noteForm = document.getElementById('noteForm');
      const noteSaveMode = document.getElementById('noteSaveMode');
      const existingNoteField = document.getElementById('existingNoteField');
      const existingNoteSelect = document.getElementById('existingNoteSelect');
      const saveModeHint = document.getElementById('saveModeHint');
      const noteTitle = document.getElementById('noteTitle');
      const noteTags = document.getElementById('noteTags');
      const noteProblem = document.getElementById('noteProblem');
      const noteRootCause = document.getElementById('noteRootCause');
      const noteSolution = document.getElementById('noteSolution');
      const noteTakeaways = document.getElementById('noteTakeaways');
      const composerNotice = document.getElementById('composerNotice');
      const regenDraftBtn = document.getElementById('regenDraftBtn');
      const saveNoteBtn = document.getElementById('saveNoteBtn');
      const WORKSPACE_PREFS_KEY = 'knowledgebase.home.workspace';
      const COMPOSER_DRAFT_KEY = 'knowledgebase.home.composerDraft';
      const APPEND_SUMMARY_KEY_PREFIX = 'knowledgebase.notes.appendSummary.';
      const AUTO_SYNC_PREFS_KEY = 'knowledgebase.home.autoSync';
      const SYNC_SOURCE_PREFS_KEY = 'knowledgebase.home.syncSources';
      const AUTO_SYNC_INTERVAL_MS = 5 * 60 * 1000;

      let autoSyncEnabled = false;
      let autoSyncIntervalId = null;
      let syncStatusPollTimerId = null;

      function cloneGroups(groups) {
        return {
          ready: [...(groups.ready || [])],
          new: [...(groups.new || [])],
          later: [...(groups.later || [])],
          done: [...(groups.done || [])],
          ignored: [...(groups.ignored || [])]
        };
      }

      function normalizeWorkspaceFilter(value, showIgnored = state.showIgnored) {
        const allowed = ['all', 'ready', 'new', 'later', 'done', ...(showIgnored ? ['ignored'] : [])];
        return allowed.includes(value) ? value : 'all';
      }

      function loadWorkspacePreferences() {
        try {
          const raw = window.localStorage.getItem(WORKSPACE_PREFS_KEY);
          if (!raw) {
            return;
          }

          const prefs = JSON.parse(raw);
          state.showIgnored = Boolean(prefs?.showIgnored);
          searchInputEl.value = typeof prefs?.search === 'string' ? prefs.search : '';
          state.activeWorkspaceFilter = normalizeWorkspaceFilter(
            String(prefs?.filter || 'all'),
            state.showIgnored
          );
          state.workspaceQuery = searchInputEl.value.trim();
        } catch (error) {
          state.showIgnored = false;
          state.activeWorkspaceFilter = 'all';
          state.workspaceQuery = '';
          searchInputEl.value = '';
        }
      }

      function persistWorkspacePreferences() {
        try {
          window.localStorage.setItem(
            WORKSPACE_PREFS_KEY,
            JSON.stringify({
              search: state.workspaceQuery,
              filter: normalizeWorkspaceFilter(state.activeWorkspaceFilter, state.showIgnored),
              showIgnored: state.showIgnored
            })
          );
        } catch (error) {
          // Ignore storage failures in private mode or restrictive environments.
        }
      }

      function loadAutoSyncPreference() {
        try {
          const raw = window.localStorage.getItem(AUTO_SYNC_PREFS_KEY);
          if (!raw) {
            autoSyncEnabled = false;
            return;
          }
          const prefs = JSON.parse(raw);
          autoSyncEnabled = Boolean(prefs?.enabled);
        } catch (error) {
          autoSyncEnabled = false;
        }
      }

      function loadSyncSourcePreference() {
        try {
          const raw = window.localStorage.getItem(SYNC_SOURCE_PREFS_KEY);
          if (!raw) {
            return;
          }
          const prefs = JSON.parse(raw);
          state.syncOptions = {
            include_vscode: prefs?.include_vscode !== false,
            include_windsurf: prefs?.include_windsurf !== false,
          };
        } catch (error) {
          state.syncOptions = {
            include_vscode: true,
            include_windsurf: true,
          };
        }
      }

      function persistAutoSyncPreference() {
        try {
          window.localStorage.setItem(
            AUTO_SYNC_PREFS_KEY,
            JSON.stringify({ enabled: autoSyncEnabled, saved_at: Date.now() })
          );
        } catch (error) {
          // Ignore storage failures in private mode or restrictive environments.
        }
      }

      function persistSyncSourcePreference() {
        try {
          window.localStorage.setItem(
            SYNC_SOURCE_PREFS_KEY,
            JSON.stringify({
              include_vscode: Boolean(state.syncOptions?.include_vscode),
              include_windsurf: Boolean(state.syncOptions?.include_windsurf),
              saved_at: Date.now()
            })
          );
        } catch (error) {
          // Ignore storage failures in private mode or restrictive environments.
        }
      }

      function selectedSyncSourceLabel() {
        const labels = [];
        if (state.syncOptions?.include_vscode) {
          labels.push('VSCode');
        }
        if (state.syncOptions?.include_windsurf) {
          labels.push('Windsurf');
        }
        return labels.length ? labels.join(' / ') : '未选择来源';
      }

      function renderSyncSourceOptions() {
        const items = [
          { key: 'include_vscode', label: 'VSCode' },
          { key: 'include_windsurf', label: 'Windsurf' },
        ];
        syncSourceList.innerHTML = items.map((item) => `
          <button
            type="button"
            class="tag-filter-btn${state.syncOptions?.[item.key] ? ' is-active' : ''}"
            data-sync-source="${escapeHtml(item.key)}"
          >
            ${escapeHtml(item.label)}
          </button>
        `).join('');
      }

      function formatSyncMetaLine(syncState) {
        const progress = syncState?.progress || {};
        if (syncState?.running && Number(progress.total_files || 0) > 0) {
          return `当前进度：${progress.processed_files || 0}/${progress.total_files || 0} 个文件 / ${progress.parsed_messages || 0} 条消息 / 新增 ${progress.inserted_messages || 0} 条 / 跳过 ${progress.skipped_files || 0} 个已同步文件。`;
        }
        const result = syncState?.last_result;
        if (!result) {
          return '支持同步 VSCode 和 Windsurf 的聊天记录；默认只提取前 200 字作为摘要，速度更快。';
        }
        return `最近一次：${result.files || 0} 个文件 / ${result.parsed || 0} 条消息 / 新增 ${result.inserted || 0} 条 / 去重 ${result.deduped || 0} 条 / 跳过 ${result.skipped_files || 0} 个已同步文件 / 耗时 ${Math.round((Number(result.elapsed_ms || 0) / 1000) * 10) / 10}s`;
      }

      function renderSyncState() {
        const syncState = state.syncState || {};
        const progress = syncState.progress || {};
        const lastResult = syncState.last_result || {};
        const insertedCount = Number(lastResult.inserted || 0);
        const skippedFiles = Number(lastResult.skipped_files || 0);
        syncIdeBtn.disabled = Boolean(syncState.running);
        syncIdeBtn.textContent = syncState.running ? '正在同步 IDE 对话...' : '立即同步 IDE 对话';
        autoSyncToggleBtn.classList.toggle('is-active', autoSyncEnabled);
        autoSyncToggleBtn.textContent = autoSyncEnabled ? '关闭自动同步' : '开启自动同步';
        renderSyncSourceOptions();

        if (syncState.running) {
          const progressLabel = Number(progress.total_files || 0) > 0
            ? `已处理 ${progress.processed_files || 0}/${progress.total_files || 0} 个文件`
            : '正在扫描本地 IDE 聊天记录';
          syncStatusText.textContent = syncState.last_started_at
            ? `同步已开始于 ${syncState.last_started_at}，${progressLabel}。`
            : `${progressLabel}，请稍候。`;
        } else if (syncState.last_error) {
          syncStatusText.textContent = `上次同步失败：${syncState.last_error}`;
        } else if (syncState.last_finished_at) {
          syncStatusText.textContent = insertedCount > 0
            ? `最近完成于 ${syncState.last_finished_at}；本次新增了 ${insertedCount} 条消息，收件箱已经更新。`
            : skippedFiles > 0
              ? `最近完成于 ${syncState.last_finished_at}；这次没有发现新 IDE 对话，已跳过 ${skippedFiles} 个已同步文件。`
              : `最近完成于 ${syncState.last_finished_at}；你可以随时再同步一次，自动同步开启后页面也会定时补拉。`;
        } else {
          syncStatusText.textContent = '还没有执行过 IDE 同步；点击下面的按钮开始导入 VSCode/Windsurf 聊天记录。';
        }

        syncMetaLine.textContent = `当前来源：${selectedSyncSourceLabel()}。${formatSyncMetaLine(syncState)}`;
      }

      function stopSyncStatusPolling() {
        if (syncStatusPollTimerId) {
          window.clearTimeout(syncStatusPollTimerId);
          syncStatusPollTimerId = null;
        }
      }

      async function fetchSyncStatus() {
        const resp = await fetch('/api/sync/ide/status');
        if (!resp.ok) {
          throw new Error(`获取同步状态失败: ${resp.status}`);
        }
        const data = await resp.json();
        state.syncState = { ...(data.state || {}) };
        renderSyncState();
        return state.syncState;
      }

      function scheduleSyncStatusPolling(options = {}) {
        const { silent = false } = options;
        stopSyncStatusPolling();
        if (!state.syncState?.running) {
          return;
        }

        syncStatusPollTimerId = window.setTimeout(async () => {
          const wasRunning = Boolean(state.syncState?.running);
          try {
            const nextState = await fetchSyncStatus();
            if (wasRunning && !nextState.running) {
              if (nextState.last_error) {
                if (!silent) {
                  setWorkspaceMessage(nextState.last_error || '同步 IDE 对话失败，请稍后再试。');
                }
              } else {
                await loadInbox();
                if (!silent) {
                  const lastResult = nextState.last_result || {};
                  const insertedCount = Number(lastResult.inserted || 0);
                  const skippedFiles = Number(lastResult.skipped_files || 0);
                  setWorkspaceMessage(
                    insertedCount > 0
                      ? `IDE 对话同步完成，已新增 ${insertedCount} 条消息并刷新收件箱。`
                      : skippedFiles > 0
                        ? `IDE 对话同步完成，本次没有新增消息；已跳过 ${skippedFiles} 个已同步文件。`
                        : 'IDE 对话同步完成，收件箱已更新。'
                  );
                }
              }
              return;
            }

            if (nextState.running) {
              scheduleSyncStatusPolling({ silent });
            }
          } catch (error) {
            state.syncState = {
              ...(state.syncState || {}),
              running: false,
              last_error: error.message || '获取同步状态失败，请稍后再试。'
            };
            renderSyncState();
            if (!silent) {
              setWorkspaceMessage(error.message || '获取同步状态失败，请稍后再试。');
            }
          }
        }, 1200);
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

      function clip(value, maxLength = 140) {
        const text = String(value || '').trim();
        return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
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

      function priorityClass(priority) {
        if (String(priority || '').includes('推荐')) {
          return 'priority-badge priority-high';
        }
        if (String(priority || '').includes('值得')) {
          return 'priority-badge priority-medium';
        }
        return 'priority-badge';
      }

      function priorityWeight(priority) {
        if (String(priority || '').includes('推荐')) {
          return 2;
        }
        if (String(priority || '').includes('值得')) {
          return 1;
        }
        return 0;
      }

      function setWorkspaceMessage(message) {
        workspaceHintEl.textContent = message;
      }

      function availableWorkspaceKeys() {
        return state.showIgnored
          ? ['ready', 'new', 'later', 'done', 'ignored']
          : ['ready', 'new', 'later', 'done'];
      }

      function visibleWorkspaceKeys() {
        return state.activeWorkspaceFilter === 'all'
          ? availableWorkspaceKeys()
          : [state.activeWorkspaceFilter];
      }

      function countItems(items) {
        return Array.isArray(items) ? items.length : 0;
      }

      function renderWorkspaceFilters(groups) {
        const items = ['all', ...availableWorkspaceKeys()];
        workspaceFilterListEl.innerHTML = items.map((key) => {
          const meta = workspaceFilterMeta[key];
          const count = key === 'all'
            ? availableWorkspaceKeys().reduce((total, groupKey) => total + countItems(groups[groupKey]), 0)
            : countItems(groups[key]);
          return `
            <button
              type="button"
              class="tag-filter-btn workspace-filter-btn${state.activeWorkspaceFilter === key ? ' is-active' : ''}"
              data-workspace-filter="${escapeHtml(key)}"
            >
              ${escapeHtml(meta.label)} · ${count}
            </button>
          `;
        }).join('');
        toggleIgnoredBtn.classList.toggle('is-active', state.showIgnored);
        toggleIgnoredBtn.textContent = state.showIgnored ? '隐藏已忽略' : '显示已忽略';
      }

      function updateWorkspaceMeta(groups) {
        const visibleCount = visibleWorkspaceKeys()
          .reduce((total, key) => total + countItems(groups[key]), 0);
        const visiblePendingCount = countItems(groups.ready) + countItems(groups.new);
        const visibleReadyCount = countItems(groups.ready);
        const filterMeta = workspaceFilterMeta[state.activeWorkspaceFilter] || workspaceFilterMeta.all;
        workspaceCountEl.textContent = state.workspaceQuery
          ? `搜索结果 ${visibleCount} 个会话`
          : `当前显示 ${visibleCount} 个会话`;
        pendingMetricEl.textContent = visiblePendingCount;
        readyMetricEl.textContent = visibleReadyCount;
        doneMetricEl.textContent = state.inboxStats.done_this_week || 0;
        setWorkspaceMessage(
          state.workspaceQuery
            ? `当前搜索“${state.workspaceQuery}”。${filterMeta.hint}`
            : filterMeta.hint
        );
      }

      function findInboxItem(source, sessionId) {
        for (const items of Object.values(state.inboxGroups)) {
          const matched = (items || []).find((item) => item.source === source && item.session_id === sessionId);
          if (matched) {
            return matched;
          }
        }
        return null;
      }

      function sessionSelectionKey(source, sessionId) {
        return `${source}::${sessionId}`;
      }

      function visibleSelectableItems() {
        return visibleWorkspaceKeys()
          .flatMap((key) => groupsForCurrentView()[key] || [])
          .filter((item) => item.status !== 'done');
      }

      function groupsForCurrentView() {
        return filterGroups();
      }

      function selectedItems() {
        return state.selectedSessionKeys
          .map((key) => {
            const [source, sessionId] = key.split('::');
            return findInboxItem(source, sessionId);
          })
          .filter(Boolean);
      }

      function pruneSelection() {
        const visibleKeys = new Set(
          visibleSelectableItems()
            .filter((item) => item.status !== 'done')
            .map((item) => sessionSelectionKey(item.source, item.session_id))
        );
        state.selectedSessionKeys = state.selectedSessionKeys.filter((key) => visibleKeys.has(key));
      }

      function toggleSessionSelection(source, sessionId) {
        const key = sessionSelectionKey(source, sessionId);
        if (state.selectedSessionKeys.includes(key)) {
          state.selectedSessionKeys = state.selectedSessionKeys.filter((item) => item !== key);
        } else {
          state.selectedSessionKeys = [...state.selectedSessionKeys, key];
        }
      }

      function clearBatchSelection() {
        state.selectedSessionKeys = [];
      }

      function renderBatchBar() {
        const count = state.selectedSessionKeys.length;
        batchActionBar.hidden = count === 0;
        batchSelectionTitle.textContent = `已选中 ${count} 条会话`;
        batchQuickSaveBtn.disabled = count === 0;
        batchConfirmBtn.disabled = count === 0;
        batchReadyBtn.disabled = count === 0;
        batchLaterBtn.disabled = count === 0;
        batchIgnoreBtn.disabled = count === 0;
      }

      function setBatchConfirmNotice(message, type = '') {
        batchConfirmNotice.textContent = message;
        batchConfirmNotice.className = type ? `notice ${type}` : 'notice';
      }

      function openBatchConfirmModal() {
        const count = state.selectedSessionKeys.length;
        if (!count) {
          return;
        }
        batchConfirmLabel.textContent = `当前选中 ${count} 条会话；会统一设置优先级，并把共用标签追加到每条会话上。`;
        batchConfirmPriority.value = '值得整理';
        batchConfirmTags.value = '';
        setBatchConfirmNotice('');
        batchConfirmShell.hidden = false;
        document.body.classList.add('composer-open');
      }

      function closeBatchConfirmModal() {
        batchConfirmForm.reset();
        setBatchConfirmNotice('');
        batchConfirmShell.hidden = true;
        document.body.classList.remove('composer-open');
      }

      function buildFocusItems() {
        const candidates = [
          ...(state.inboxGroups.ready || []),
          ...(state.inboxGroups.new || [])
        ];

        return candidates
          .slice()
          .sort((left, right) => {
            const priorityGap = priorityWeight(right.display_priority) - priorityWeight(left.display_priority);
            if (priorityGap !== 0) {
              return priorityGap;
            }
            const confidenceGap = Number(right.ai_confidence || 0) - Number(left.ai_confidence || 0);
            if (confidenceGap !== 0) {
              return confidenceGap;
            }
            return String(right.latest_created_at || '').localeCompare(String(left.latest_created_at || ''));
          })
          .slice(0, 5);
      }

      function parseTagInput(value) {
        return String(value || '')
          .split(/[,\uFF0C]/)
          .map((item) => item.trim())
          .filter(Boolean);
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

      function formatNoteOptionLabel(note) {
        const parts = [
          note.title || `笔记 ${note.id}`,
          note.status_label || note.status || '草稿',
          note.updated_at ? `更新于 ${note.updated_at}` : '',
          Number(note.source_count || 0) ? `${note.source_count} 条来源` : '',
          Array.isArray(note.tags) && note.tags.length ? `标签：${note.tags.join(' / ')}` : ''
        ].filter(Boolean);
        return parts.join(' · ');
      }

      function renderExistingNoteOptions(selectedId = '') {
        const selected = String(selectedId || '');
        const options = [
          '<option value="">选择一篇已有笔记</option>',
          ...state.noteOptions.map((note) => `
            <option value="${escapeHtml(note.id)}"${String(note.id) === selected ? ' selected' : ''}>
              ${escapeHtml(formatNoteOptionLabel(note))}
            </option>
          `)
        ];
        existingNoteSelect.innerHTML = options.join('');
      }

      function updateSaveModeUi() {
        const appendMode = noteSaveMode.value === 'append';
        existingNoteField.hidden = !appendMode;
        existingNoteSelect.required = appendMode;
        saveNoteBtn.textContent = appendMode ? '追加到已有笔记' : '保存笔记';
        saveModeHint.textContent = appendMode
          ? '追加时会合并正文、补充来源，并把这篇笔记重新标记为草稿，方便你稍后复核。'
          : '默认会新建一篇草稿；如果这是同主题补充，也可以追加到已有笔记。';
      }

      function renderInboxCard(item) {
        const selectionKey = sessionSelectionKey(item.source, item.session_id);
        const isSelected = state.selectedSessionKeys.includes(selectionKey);
        const tags = (item.display_tags || []).map((tag) => `<span class="mini-tag">${escapeHtml(tag)}</span>`).join('');
        const title = item.display_title || item.session_id;
        const statusBadge = item.status === 'done'
          ? '<span class="pill">已完成</span>'
          : item.status === 'ignored'
            ? '<span class="pill">已忽略</span>'
          : `<span class="pill">${escapeHtml(item.message_count)} 条</span>`;
        let actions = `
          <button
            type="button"
            class="ghost-button open-session-record"
            data-source="${escapeHtml(item.source)}"
            data-session-id="${escapeHtml(item.session_id)}"
            data-title="${escapeHtml(title)}"
          >
            查看完整记录
          </button>
        `;

        if (item.status === 'ignored') {
          actions += `
            <button
              type="button"
              class="ghost-button mark-inbox-ready"
              data-source="${escapeHtml(item.source)}"
              data-session-id="${escapeHtml(item.session_id)}"
            >
              恢复待办
            </button>
          `;
        } else if (item.status !== 'done') {
          actions += `
            <button
              type="button"
              class="secondary-btn quick-save-session-note"
              data-source="${escapeHtml(item.source)}"
              data-session-id="${escapeHtml(item.session_id)}"
            >
              一键存草稿
            </button>
            <button
              type="button"
              class="secondary-btn open-session-note"
              data-source="${escapeHtml(item.source)}"
              data-session-id="${escapeHtml(item.session_id)}"
              data-title="${escapeHtml(title)}"
            >
              整理
            </button>
            <button
              type="button"
              class="ghost-button open-inbox-confirm"
              data-source="${escapeHtml(item.source)}"
              data-session-id="${escapeHtml(item.session_id)}"
            >
              确认建议
            </button>
          `;

          if (item.status === 'later') {
            actions += `
              <button
                type="button"
                class="ghost-button mark-inbox-ready"
                data-source="${escapeHtml(item.source)}"
                data-session-id="${escapeHtml(item.session_id)}"
              >
                恢复待办
              </button>
            `;
          } else {
            actions += `
              <button
                type="button"
                class="ghost-button mark-inbox-later"
                data-source="${escapeHtml(item.source)}"
                data-session-id="${escapeHtml(item.session_id)}"
              >
                稍后
              </button>
              <button
                type="button"
                class="danger-button mark-inbox-ignore"
                data-source="${escapeHtml(item.source)}"
                data-session-id="${escapeHtml(item.session_id)}"
              >
                忽略
              </button>
            `;
          }
        } else {
          actions += `
            ${item.note_id ? `
              <a
                class="secondary-btn"
                href="/notes?note_id=${encodeURIComponent(item.note_id)}"
              >
                打开笔记
              </a>
            ` : ''}
            <button
              type="button"
              class="ghost-button mark-inbox-ready"
              data-source="${escapeHtml(item.source)}"
              data-session-id="${escapeHtml(item.session_id)}"
            >
              重新打开
            </button>
            <a class="ghost-button" href="/notes">查看笔记库</a>
          `;
        }

        return `
          <article class="browser-card session-browser-card inbox-card inbox-status-${escapeHtml(item.status)}${isSelected ? ' is-selected' : ''}">
            <header class="browser-head">
              <div>
                <p class="browser-kicker">${escapeHtml(item.source)} · ${escapeHtml(item.length_label || '')}</p>
                <h3 class="browser-title">${escapeHtml(title)}</h3>
              </div>
              <div class="card-badges">
                ${item.status !== 'done' ? `
                  <label class="inline-meta inline-meta-tight">
                    <input
                      type="checkbox"
                      class="session-select-toggle"
                      data-source="${escapeHtml(item.source)}"
                      data-session-id="${escapeHtml(item.session_id)}"
                      ${isSelected ? 'checked' : ''}
                    />
                    <span>选择</span>
                  </label>
                ` : ''}
                <span class="${priorityClass(item.display_priority)}">${escapeHtml(item.display_priority || '待判断')}</span>
                ${statusBadge}
              </div>
            </header>
            <p class="browser-text">${escapeHtml(item.display_excerpt || '（暂无摘要）')}</p>
            <div class="inline-meta inline-meta-card">
              <span>${escapeHtml(item.display_reason || '')}</span>
              <span>${escapeHtml(item.session_id)}</span>
              ${tags || '<span class="mini-tag mini-tag-muted">待补标签</span>'}
            </div>
            <footer class="browser-foot">
              <span>${escapeHtml(item.latest_created_at || '')}</span>
              <div class="inline-actions">${actions}</div>
            </footer>
          </article>
        `;
      }

      function renderFocusCard(item, index) {
        const selectionKey = sessionSelectionKey(item.source, item.session_id);
        const isSelected = state.selectedSessionKeys.includes(selectionKey);
        return `
          <article class="browser-card focus-card inbox-status-${escapeHtml(item.status)}${isSelected ? ' is-selected' : ''}">
            <header class="browser-head">
              <div>
                <p class="browser-kicker">建议 ${index + 1} · ${escapeHtml(item.source)} · ${escapeHtml(item.length_label || '')}</p>
                <h3 class="browser-title">${escapeHtml(item.display_title || item.session_id)}</h3>
              </div>
              <div class="inline-actions">
                <label class="inline-meta inline-meta-tight">
                  <input
                    type="checkbox"
                    class="session-select-toggle"
                    data-source="${escapeHtml(item.source)}"
                    data-session-id="${escapeHtml(item.session_id)}"
                    ${isSelected ? 'checked' : ''}
                  />
                  <span>选择</span>
                </label>
                <span class="${priorityClass(item.display_priority)}">${escapeHtml(item.display_priority || '待判断')}</span>
              </div>
            </header>
            <p class="browser-text">${escapeHtml(item.display_reason || '先整理这一条，能更快形成一篇可复用笔记。')}</p>
            <div class="inline-meta inline-meta-card">
              <span>${escapeHtml(item.message_count)} 条消息</span>
              <span>${escapeHtml(item.latest_created_at || '')}</span>
            </div>
            <footer class="browser-foot">
              <div class="inline-actions">
                <button
                  type="button"
                  class="secondary-btn quick-save-session-note"
                  data-source="${escapeHtml(item.source)}"
                  data-session-id="${escapeHtml(item.session_id)}"
                >
                  一键存草稿
                </button>
                <button
                  type="button"
                  class="ghost-button open-session-note"
                  data-source="${escapeHtml(item.source)}"
                  data-session-id="${escapeHtml(item.session_id)}"
                  data-title="${escapeHtml(item.display_title || item.session_id)}"
                >
                  进入编辑
                </button>
                <button
                  type="button"
                  class="ghost-button open-session-record"
                  data-source="${escapeHtml(item.source)}"
                  data-session-id="${escapeHtml(item.session_id)}"
                  data-title="${escapeHtml(item.display_title || item.session_id)}"
                >
                  查看记录
                </button>
              </div>
            </footer>
          </article>
        `;
      }

      function renderFocusStrip() {
        const items = buildFocusItems();
        focusCountEl.textContent = `${items.length} 条建议`;
        if (!items.length) {
          focusListEl.innerHTML = `
            <div class="empty-state compact">
              <h3>今天没有新的优先项</h3>
              <p>先去笔记库回看最近沉淀的内容，或者刷新收件箱继续抓取新会话。</p>
            </div>
          `;
          return;
        }

        focusListEl.innerHTML = items.map(renderFocusCard).join('');
      }

      function filterGroups() {
        const filtered = cloneGroups(state.inboxGroups);

        if (state.activeWorkspaceFilter !== 'all') {
          for (const key of ['ready', 'new', 'later', 'done', 'ignored']) {
            if (key !== state.activeWorkspaceFilter) {
              filtered[key] = [];
            }
          }
        }
        return filtered;
      }

      function renderGroupSection(key, items) {
        const meta = sectionMeta[key];
        const list = items.length
          ? items.map(renderInboxCard).join('')
          : `
            <div class="empty-state compact">
              <h3>当前没有内容</h3>
              <p>${escapeHtml(meta.hint)}</p>
            </div>
          `;

        return `
          <section class="inbox-section">
            <header class="compact-header inbox-section-header">
              <div>
                <p class="eyebrow">${escapeHtml(meta.title)}</p>
                <h2>${escapeHtml(meta.title)}</h2>
                <p class="panel-text">${escapeHtml(meta.hint)}</p>
              </div>
              <div class="panel-badge">${items.length} 条</div>
            </header>
            <div class="inbox-card-list">
              ${list}
            </div>
          </section>
        `;
      }

      function renderWorkspace() {
        renderFocusStrip();
        const groups = filterGroups();
        pruneSelection();
        renderBatchBar();
        renderWorkspaceFilters(groups);
        updateWorkspaceMeta(groups);
        persistWorkspacePreferences();
        const visibleCount = visibleWorkspaceKeys()
          .reduce((total, key) => total + (groups[key] || []).length, 0);

        if (!visibleCount) {
          const filterLabel = (workspaceFilterMeta[state.activeWorkspaceFilter] || workspaceFilterMeta.all).label;
          browserResultsEl.innerHTML = `
            <section class="empty-state">
              <h2>没有找到匹配的会话</h2>
              <p>${state.workspaceQuery
                ? `搜索词是“${escapeHtml(state.workspaceQuery)}”，当前筛选是“${escapeHtml(filterLabel)}”。可以换个关键词，或者点击“重置”查看全部收件箱内容。`
                : `当前筛选是“${escapeHtml(filterLabel)}”。换一个关键词试试，或者点击“重置”查看全部收件箱内容。`}</p>
            </section>
          `;
          return;
        }

        browserResultsEl.innerHTML = visibleWorkspaceKeys()
          .map((key) => renderGroupSection(key, groups[key] || []))
          .join('');
      }

      function syncInboxState(data) {
        state.inboxGroups = cloneGroups(data.groups || {});
        state.inboxStats = { ...(data.stats || {}) };
      }

      function setBatchBusy(isBusy) {
        batchQuickSaveBtn.disabled = isBusy || state.selectedSessionKeys.length === 0;
        batchConfirmBtn.disabled = isBusy || state.selectedSessionKeys.length === 0;
        batchReadyBtn.disabled = isBusy || state.selectedSessionKeys.length === 0;
        batchLaterBtn.disabled = isBusy || state.selectedSessionKeys.length === 0;
        batchIgnoreBtn.disabled = isBusy || state.selectedSessionKeys.length === 0;
        clearBatchSelectionBtn.disabled = isBusy || state.selectedSessionKeys.length === 0;
      }

      async function runBatchAction(action) {
        const items = selectedItems();
        if (!items.length) {
          return;
        }

        const actionLabel = action === 'ready'
          ? '恢复待办'
          : action === 'later'
            ? '稍后处理'
            : action === 'quick_save'
              ? '存草稿'
              : '忽略';

        setBatchBusy(true);
        setWorkspaceMessage(`正在批量${actionLabel}...`);
        try {
          const resp = await fetch('/api/inbox/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              action,
              items: items.map((item) => ({ source: item.source, session_id: item.session_id }))
            })
          });
          if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            throw new Error(data?.detail || `批量处理失败: ${resp.status}`);
          }

          const data = await resp.json();
          clearBatchSelection();
          await loadInbox();
          if (action === 'quick_save') {
            const reusedCount = Number(data?.reused_count || 0);
            const createdCount = Number(data?.count || 0) - reusedCount;
            setWorkspaceMessage(`已批量存成 ${data?.count || items.length} 篇草稿（新建 ${createdCount} 篇，复用 ${reusedCount} 篇）。`);
          } else {
            setWorkspaceMessage(`已批量${actionLabel} ${items.length} 条会话。`);
          }
        } catch (error) {
          setWorkspaceMessage(error.message || '批量处理失败，请稍后再试。');
        } finally {
          setBatchBusy(false);
          renderBatchBar();
        }
      }

      async function runIdeSync(options = {}) {
        const { silent = false } = options;
        if (state.syncState?.running) {
          scheduleSyncStatusPolling({ silent });
          return;
        }

        state.syncState = {
          ...(state.syncState || {}),
          running: true,
          last_error: '',
          progress: {
            total_files: 0,
            processed_files: 0,
            parsed_messages: 0,
            inserted_messages: 0,
            current_source: '',
            current_file: ''
          }
        };
        renderSyncState();
        if (!silent) {
          setWorkspaceMessage('已开始后台同步 IDE 对话，正在扫描本地聊天记录...');
        }

        try {
          const resp = await fetch('/api/sync/ide', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              include_vscode: Boolean(state.syncOptions?.include_vscode),
              include_windsurf: Boolean(state.syncOptions?.include_windsurf),
            })
          });
          if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            throw new Error(data?.detail || `同步失败: ${resp.status}`);
          }

          const data = await resp.json();
          state.syncState = { ...(data.state || {}) };
          renderSyncState();
          if (state.syncState?.running) {
            scheduleSyncStatusPolling({ silent });
          } else {
            await loadInbox();
            if (!silent) {
              const lastResult = state.syncState.last_result || {};
              const insertedCount = Number(lastResult.inserted || 0);
              const skippedFiles = Number(lastResult.skipped_files || 0);
              setWorkspaceMessage(
                insertedCount > 0
                  ? `IDE 对话同步完成，已新增 ${insertedCount} 条消息并刷新收件箱。`
                  : skippedFiles > 0
                    ? `IDE 对话同步完成，本次没有新增消息；已跳过 ${skippedFiles} 个已同步文件。`
                    : 'IDE 对话同步完成，收件箱已更新。'
              );
            }
          }
        } catch (error) {
          stopSyncStatusPolling();
          state.syncState = {
            ...(state.syncState || {}),
            running: false,
            last_error: error.message || '同步失败，请稍后再试。'
          };
          renderSyncState();
          if (!silent) {
            setWorkspaceMessage(error.message || '同步 IDE 对话失败，请稍后再试。');
          }
        }
      }

      function stopAutoSyncTimer() {
        if (autoSyncIntervalId) {
          window.clearInterval(autoSyncIntervalId);
          autoSyncIntervalId = null;
        }
      }

      function startAutoSyncTimer() {
        stopAutoSyncTimer();
        if (!autoSyncEnabled) {
          return;
        }
        autoSyncIntervalId = window.setInterval(() => {
          if (document.hidden) {
            return;
          }
          runIdeSync({ silent: true }).catch(() => {
            // Background sync failures are surfaced in the sync card.
          });
        }, AUTO_SYNC_INTERVAL_MS);
      }

      async function loadInbox(options = {}) {
        const { withRefresh = false } = options;
        refreshInboxBtn.disabled = true;
        try {
          if (withRefresh) {
            setWorkspaceMessage('正在刷新收件箱...');
            const refreshResp = await fetch('/api/inbox/refresh', { method: 'POST' });
            if (!refreshResp.ok) {
              throw new Error(`刷新失败: ${refreshResp.status}`);
            }
          }

          const params = new URLSearchParams();
          params.set('limit_per_group', '200');
          params.set('include_ignored', state.showIgnored ? 'true' : 'false');
          if (state.workspaceQuery) {
            params.set('q', state.workspaceQuery);
          }

          const resp = await fetch(`/api/inbox?${params.toString()}`);
          if (!resp.ok) {
            throw new Error(`加载收件箱失败: ${resp.status}`);
          }
          const data = await resp.json();
          syncInboxState(data);
          renderWorkspace();
        } finally {
          refreshInboxBtn.disabled = false;
        }
      }

      async function submitWorkspaceSearch() {
        state.workspaceQuery = searchInputEl.value.trim();
        setWorkspaceMessage(state.workspaceQuery ? '正在搜索收件箱...' : '正在恢复全部收件箱内容...');
        await loadInbox();
      }

      function setConfirmNotice(message, type = '') {
        confirmNotice.textContent = message;
        confirmNotice.className = type ? `notice ${type}` : 'notice';
      }

      function openConfirmModal(source, sessionId) {
        const item = findInboxItem(source, sessionId);
        state.activeConfirmSession = { source, session_id: sessionId };
        confirmSessionLabel.textContent = `来源：${source} · 会话 ${sessionId}`;
        confirmTitle.value = item?.display_title || '';
        confirmTags.value = (item?.display_tags || []).join(', ');
        confirmPriority.value = ['推荐优先整理', '值得整理', '可稍后整理'].includes(item?.display_priority)
          ? item.display_priority
          : '值得整理';
        setConfirmNotice('');
        confirmShell.hidden = false;
        document.body.classList.add('composer-open');
      }

      function closeConfirmModal() {
        state.activeConfirmSession = null;
        confirmForm.reset();
        setConfirmNotice('');
        confirmShell.hidden = true;
        document.body.classList.remove('composer-open');
      }

      function setNotice(message, type = '') {
        composerNotice.textContent = message;
        composerNotice.className = type ? `notice ${type}` : 'notice';
      }

      function composerDraftSignature(mode, payload) {
        if (mode === 'session') {
          return `session:${payload.source}:${payload.session_id}`;
        }
        return `message:${(payload.message_ids || []).join(',')}`;
      }

      function getComposerFormData() {
        return {
          title: noteTitle.value,
          tags: noteTags.value,
          problem: noteProblem.value,
          root_cause: noteRootCause.value,
          solution: noteSolution.value,
          key_takeaways: noteTakeaways.value
        };
      }

      function getComposerDraftMeta() {
        return {
          save_mode: noteSaveMode.value,
          existing_note_id: existingNoteSelect.value
        };
      }

      function hasComposerDraftContent(data = getComposerFormData()) {
        return Object.values(data).some((value) => String(value || '').trim());
      }

      function loadComposerDraft(signature) {
        try {
          const raw = window.localStorage.getItem(COMPOSER_DRAFT_KEY);
          if (!raw) {
            return null;
          }

          const draft = JSON.parse(raw);
          if (!draft || draft.signature !== signature || !hasComposerDraftContent(draft.fields || {})) {
            return null;
          }
          return {
            fields: draft.fields || {},
            meta: draft.meta || {}
          };
        } catch (error) {
          return null;
        }
      }

      function persistComposerDraft() {
        if (!state.activeDraftSignature) {
          return;
        }

        const fields = getComposerFormData();
        const meta = getComposerDraftMeta();
        try {
          if (!hasComposerDraftContent(fields)) {
            window.localStorage.removeItem(COMPOSER_DRAFT_KEY);
            return;
          }

          window.localStorage.setItem(
            COMPOSER_DRAFT_KEY,
            JSON.stringify({
              signature: state.activeDraftSignature,
              mode: state.activeDraftMode,
              payload: state.activeDraftPayload,
              fields,
              meta
            })
          );
        } catch (error) {
          // Ignore storage failures in private mode or restrictive environments.
        }
      }

      function clearComposerDraft() {
        try {
          window.localStorage.removeItem(COMPOSER_DRAFT_KEY);
        } catch (error) {
          // Ignore storage failures in private mode or restrictive environments.
        }
      }

      function shouldWarnBeforeClosingComposer() {
        return !composerShell.hidden && hasComposerDraftContent();
      }

      function requestCloseComposer() {
        if (
          shouldWarnBeforeClosingComposer() &&
          !window.confirm('当前整理面板里有未保存内容，关闭后仍可稍后恢复本地草稿。确定关闭吗？')
        ) {
          return;
        }
        closeComposer();
      }

      function fillDraft(draft) {
        noteTitle.value = draft.title || '';
        noteTags.value = draft.tags || '';
        noteProblem.value = draft.problem || '';
        noteRootCause.value = draft.root_cause || '';
        noteSolution.value = draft.solution || '';
        noteTakeaways.value = draft.key_takeaways || '';
      }

      function setBusy(isBusy) {
        regenDraftBtn.disabled = isBusy;
        saveNoteBtn.disabled = isBusy;
        noteSaveMode.disabled = isBusy;
        existingNoteSelect.disabled = isBusy;
      }

      function renderSourcePreview() {
        composerSourceCount.textContent = `${state.activeSources.length} 条来源`;
        if (!state.activeSources.length) {
          sourcePreviewList.innerHTML = '<p class="source-empty">选择素材后，这里会显示本次整理的对话片段。</p>';
          return;
        }

        const preview = state.activeSources.slice(0, 4).map((item) => `
          <article class="source-item">
            <header>
              <span class="source-badge">${escapeHtml(item.role)}</span>
              <span>${escapeHtml(item.source)}${item.session_id ? ` / ${escapeHtml(item.session_id)}` : ''}</span>
            </header>
            <p>${escapeHtml(clip(item.content, 180))}</p>
          </article>
        `).join('');

        const extra = state.activeSources.length > 4
          ? `<p class="source-more">还有 ${state.activeSources.length - 4} 条来源未展开显示。</p>`
          : '';

        sourcePreviewList.innerHTML = preview + extra;
      }

      function prefillComposerTagsFromSources() {
        if (noteTags.value.trim()) {
          return;
        }

        const sessionKeys = [...new Set(
          state.activeSources
            .filter((item) => item.source && item.session_id)
            .map((item) => `${item.source}::${item.session_id}`)
        )];
        if (sessionKeys.length !== 1) {
          return;
        }

        const [source, sessionId] = sessionKeys[0].split('::');
        const inboxItem = findInboxItem(source, sessionId);
        if (!inboxItem || !Array.isArray(inboxItem.display_tags) || !inboxItem.display_tags.length) {
          return;
        }
        noteTags.value = inboxItem.display_tags.join(', ');
      }

      function renderRecommendationList() {
        const items = state.activeRecommendations || [];
        noteRecommendationCount.textContent = `${items.length} 条`;
        if (!state.noteOptions.length) {
          noteRecommendationList.innerHTML = '<p class="source-empty">还没有已有笔记，先沉淀出第一篇再回来追加。</p>';
          return;
        }
        if (!items.length) {
          noteRecommendationList.innerHTML = '<p class="source-empty">暂时没有明显相似的已有笔记，适合直接新建。</p>';
          return;
        }

        noteRecommendationList.innerHTML = items.map((item) => {
          const tags = (item.tags || [])
            .map((tag) => `<span class="mini-tag note-tag">${escapeHtml(tag)}</span>`)
            .join('');
          return `
            <article class="recommendation-card">
              <header class="browser-head">
                <div>
                  <h4>${escapeHtml(item.title || `笔记 ${item.id}`)}</h4>
                  <div class="inline-meta inline-meta-tight recommendation-meta">
                    <span>${escapeHtml(item.status_label || item.status || '草稿')}</span>
                    <span>${escapeHtml(item.source_count || 0)} 条来源</span>
                    <span>${escapeHtml(item.updated_at || '')}</span>
                  </div>
                </div>
                <button
                  type="button"
                  class="ghost-button pick-recommended-note"
                  data-note-id="${escapeHtml(item.id)}"
                >
                  追加到这篇
                </button>
              </header>
              <p class="panel-text">${escapeHtml(item.match_reason || '可能是同一主题的后续补充')}</p>
              ${tags ? `<div class="note-tag-row">${tags}</div>` : ''}
            </article>
          `;
        }).join('');
      }

      function recommendationPayload() {
        return {
          title: noteTitle.value.trim(),
          tags: parseTagInput(noteTags.value),
          problem: noteProblem.value.trim(),
          root_cause: noteRootCause.value.trim(),
          solution: noteSolution.value.trim(),
          key_takeaways: noteTakeaways.value.trim(),
          limit: 5
        };
      }

      function hasRecommendationSignal(payload = recommendationPayload()) {
        return Boolean(
          payload.title ||
          payload.tags.length ||
          payload.problem ||
          payload.root_cause ||
          payload.solution ||
          payload.key_takeaways
        );
      }

      async function loadNoteRecommendations() {
        if (!state.activeDraftSignature) {
          state.activeRecommendations = [];
          renderRecommendationList();
          return;
        }
        if (!state.noteOptions.length) {
          state.activeRecommendations = [];
          renderRecommendationList();
          return;
        }

        const payload = recommendationPayload();
        if (!hasRecommendationSignal(payload)) {
          state.activeRecommendations = [];
          renderRecommendationList();
          return;
        }

        const requestSignature = state.activeDraftSignature;
        noteRecommendationCount.textContent = '...';
        noteRecommendationList.innerHTML = '<p class="source-empty">正在查找相似笔记...</p>';
        try {
          const resp = await fetch('/api/notes/recommend', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          if (!resp.ok) {
            throw new Error(`推荐失败: ${resp.status}`);
          }
          const data = await resp.json();
          if (requestSignature !== state.activeDraftSignature) {
            return;
          }
          state.activeRecommendations = Array.isArray(data.items) ? data.items : [];
          renderRecommendationList();
        } catch (error) {
          if (requestSignature !== state.activeDraftSignature) {
            return;
          }
          state.activeRecommendations = [];
          noteRecommendationCount.textContent = '0 条';
          noteRecommendationList.innerHTML = '<p class="source-empty">暂时无法加载相似笔记推荐。</p>';
        }
      }

      function openComposerBase(mode, payload, metaText) {
        state.activeDraftMode = mode;
        state.activeDraftPayload = payload;
        state.activeDraftSignature = composerDraftSignature(mode, payload);
        state.activeMessageIds = mode === 'message' ? [...payload.message_ids] : [];
        state.activeSources = [];
        state.activeRecommendations = [];
        noteForm.reset();
        noteSaveMode.value = 'new';
        renderExistingNoteOptions('');
        updateSaveModeUi();
        composerModePill.textContent = mode === 'session' ? '整段会话' : '筛选消息';
        composerSourceMeta.textContent = metaText;
        renderSourcePreview();
        renderRecommendationList();
        const defaultItem = mode === 'session'
          ? findInboxItem(payload.source, payload.session_id)
          : null;
        noteTags.value = defaultItem && Array.isArray(defaultItem.display_tags)
          ? defaultItem.display_tags.join(', ')
          : '';
        const restoredDraft = loadComposerDraft(state.activeDraftSignature);
        if (restoredDraft) {
          fillDraft(restoredDraft.fields || {});
          noteSaveMode.value = restoredDraft.meta?.save_mode === 'append' ? 'append' : 'new';
          renderExistingNoteOptions(restoredDraft.meta?.existing_note_id || '');
          updateSaveModeUi();
          setNotice('已恢复本地草稿，正在同步来源消息。', 'success');
        } else {
          setNotice('');
        }
        composerShell.hidden = false;
        document.body.classList.add('composer-open');
        return Boolean(restoredDraft);
      }

      function openComposerForSession(source, sessionId, title = '') {
        const restoredDraft = openComposerBase(
          'session',
          { source, session_id: sessionId },
          `来源：${source} · ${title || `会话 ${sessionId}`}`
        );
        generateDraft({ preserveExisting: restoredDraft });
      }

      function openComposerForMessages(messageIds, metaText) {
        const restoredDraft = openComposerBase('message', { message_ids: messageIds }, metaText);
        generateDraft({ preserveExisting: restoredDraft });
      }

      function openComposerFromQueryIfNeeded() {
        const source = String(queryParams.get('compose_source') || '').trim();
        const sessionId = String(queryParams.get('compose_session_id') || '').trim();
        const title = String(queryParams.get('compose_title') || '').trim();
        if (!source || !sessionId) {
          return;
        }

        openComposerForSession(source, sessionId, title);
        queryParams.delete('compose_source');
        queryParams.delete('compose_session_id');
        queryParams.delete('compose_title');
        const nextQuery = queryParams.toString();
        const nextUrl = `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ''}`;
        window.history.replaceState({}, '', nextUrl);
      }

      function isLikelyKeyPointMessage(item) {
        const content = String(item.content || '');
        const signal = /建议|结论|根因|原因|方案|修复|解决|应该|需要|可以|风险|报错|问题|invalid|should|issue|fix|error|warning|remove|avoid|幂等|重试|补偿/i;
        if (item.role === 'assistant' || item.role === 'system') {
          return content.length >= 18 || signal.test(content);
        }
        return signal.test(content) || content.length >= 120;
      }

      function updateRecordFilterUi() {
        document.querySelectorAll('.record-role-filter').forEach((button) => {
          button.classList.toggle('is-active', button.dataset.role === state.recordRole);
        });
        recordKeyToggleBtn.classList.toggle('is-active', state.recordKeyOnly);
        recordKeyToggleBtn.textContent = state.recordKeyOnly ? '显示全部消息' : '只看关键结论';
      }

      function filteredRecordMessages() {
        const keyword = state.recordSearch.trim().toLowerCase();
        return state.activeRecordMessages.filter((item) => {
          if (state.recordRole !== 'all' && item.role !== state.recordRole) {
            return false;
          }
          if (state.recordKeyOnly && !isLikelyKeyPointMessage(item)) {
            return false;
          }
          if (!keyword) {
            return true;
          }

          return `${item.role} ${item.content} ${item.summary || ''}`.toLowerCase().includes(keyword);
        });
      }

      function renderTranscript(items) {
        if (!items.length) {
          recordList.innerHTML = '<p class="source-empty">当前筛选条件下没有可展示的消息。</p>';
          return;
        }

        const keyword = state.recordSearch.trim();
        recordList.innerHTML = items.map((item) => `
          <article class="transcript-item transcript-role-${escapeHtml(item.role || 'unknown')}">
            <header class="transcript-meta">
              <div class="inline-meta inline-meta-tight">
                <span class="source-badge">${escapeHtml(item.role)}</span>
                <span>${escapeHtml(item.source)}${item.session_id ? ` / ${escapeHtml(item.session_id)}` : ''}</span>
              </div>
              <span>${escapeHtml(item.created_at)}</span>
            </header>
            <div class="transcript-text">${highlightText(item.content, keyword)}</div>
          </article>
        `).join('');
      }

      function applyRecordFilters() {
        updateRecordFilterUi();
        const items = filteredRecordMessages();
        state.activeRecordFilteredMessages = items;
        const total = state.activeRecordMessages.length;
        recordMeta.textContent = `来源：${state.activeRecordSession?.source || ''} · 当前显示 ${items.length} / ${total} 条消息`;
        recordComposeFilteredBtn.disabled = items.length === 0;
        recordComposeFilteredBtn.textContent = items.length ? `整理当前筛选结果（${items.length}条）` : '整理当前筛选结果';
        renderTranscript(items);
      }

      function openRecordShell(source, sessionId, title = '') {
        state.activeRecordSession = { source, session_id: sessionId, title };
        state.activeRecordMessages = [];
        state.activeRecordFilteredMessages = [];
        state.recordSearch = '';
        state.recordRole = 'all';
        state.recordKeyOnly = false;
        recordSearchInput.value = '';
        updateRecordFilterUi();
        recordTitle.textContent = title || `会话 ${sessionId}`;
        recordMeta.textContent = `来源：${source} · 正在加载完整消息记录。`;
        recordList.innerHTML = '<p class="source-empty">正在加载完整记录...</p>';
        recordShell.hidden = false;
        document.body.classList.add('composer-open');
      }

      function closeRecordShell() {
        state.activeRecordSession = null;
        state.activeRecordMessages = [];
        state.activeRecordFilteredMessages = [];
        state.recordSearch = '';
        state.recordRole = 'all';
        state.recordKeyOnly = false;
        recordShell.hidden = true;
        document.body.classList.remove('composer-open');
      }

      async function loadSessionRecord(source, sessionId, title = '') {
        openRecordShell(source, sessionId, title);

        try {
          const url = `/api/sessions/messages?source=${encodeURIComponent(source)}&session_id=${encodeURIComponent(sessionId)}`;
          const resp = await fetch(url);
          if (!resp.ok) {
            throw new Error(`加载失败: ${resp.status}`);
          }

          const data = await resp.json();
          state.activeRecordMessages = data.items || [];
          applyRecordFilters();
        } catch (error) {
          recordMeta.textContent = error.message || '加载完整记录失败，请稍后再试。';
          recordList.innerHTML = '<p class="source-empty">未能加载完整记录。</p>';
        }
      }

      function closeComposer() {
        composerShell.hidden = true;
        document.body.classList.remove('composer-open');
        state.activeDraftMode = null;
        state.activeDraftPayload = null;
        state.activeDraftSignature = '';
        state.activeMessageIds = [];
        state.activeSources = [];
        state.activeRecommendations = [];
        noteForm.reset();
        renderExistingNoteOptions('');
        updateSaveModeUi();
        renderSourcePreview();
        renderRecommendationList();
        setNotice('');
      }

      async function generateDraft(options = {}) {
        const { preserveExisting = false } = options;
        if (!state.activeDraftMode || !state.activeDraftPayload) return;

        const requestSignature = state.activeDraftSignature;
        setBusy(true);
        setNotice('正在生成结构化草稿...');

        try {
          const endpoint = state.activeDraftMode === 'session'
            ? '/api/notes/generate/session'
            : '/api/notes/generate';
          const resp = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(state.activeDraftPayload)
          });

          if (!resp.ok) {
            throw new Error(`生成失败: ${resp.status}`);
          }

          const data = await resp.json();
          if (requestSignature !== state.activeDraftSignature) {
            return;
          }
          state.activeSources = data.sources || [];
          state.activeMessageIds = state.activeSources.map((item) => item.id);
          renderSourcePreview();
          if (!(preserveExisting && requestSignature === state.activeDraftSignature && hasComposerDraftContent())) {
            fillDraft(data.draft || {});
          }
          prefillComposerTagsFromSources();
          if (state.activeDraftMode === 'session') {
            composerSourceMeta.textContent = `来源：${state.activeDraftPayload.source} · 会话 ${state.activeDraftPayload.session_id} · 已载入 ${state.activeMessageIds.length} 条消息`;
          }
          persistComposerDraft();
          loadNoteRecommendations().catch(() => {
            noteRecommendationCount.textContent = '0 条';
            noteRecommendationList.innerHTML = '<p class="source-empty">暂时无法加载相似笔记推荐。</p>';
          });
          setNotice(
            preserveExisting && requestSignature === state.activeDraftSignature
              ? '已恢复本地草稿，同时重新载入了来源消息。'
              : '草稿已生成，可以直接修改后保存。',
            'success'
          );
        } catch (error) {
          if (requestSignature !== state.activeDraftSignature) {
            return;
          }
          renderSourcePreview();
          setNotice(error.message || '生成草稿失败，请稍后再试。', 'error');
        } finally {
          if (requestSignature === state.activeDraftSignature) {
            setBusy(false);
          }
        }
      }

      document.getElementById('searchBtn').addEventListener('click', () => {
        submitWorkspaceSearch().catch((error) => {
          setWorkspaceMessage(error.message || '搜索收件箱失败，请稍后再试。');
        });
      });
      document.getElementById('resetBtn').addEventListener('click', () => {
        searchInputEl.value = '';
        submitWorkspaceSearch().catch((error) => {
          setWorkspaceMessage(error.message || '恢复收件箱失败，请稍后再试。');
        });
      });
      workspaceFilterListEl.addEventListener('click', (event) => {
        const button = event.target.closest('[data-workspace-filter]');
        if (!button) {
          return;
        }
        state.activeWorkspaceFilter = button.dataset.workspaceFilter || 'all';
        renderWorkspace();
      });
      toggleIgnoredBtn.addEventListener('click', async () => {
        const previousShowIgnored = state.showIgnored;
        const previousFilter = state.activeWorkspaceFilter;
        toggleIgnoredBtn.disabled = true;
        state.showIgnored = !state.showIgnored;
        if (!state.showIgnored && state.activeWorkspaceFilter === 'ignored') {
          state.activeWorkspaceFilter = 'all';
        }
        setWorkspaceMessage(state.showIgnored ? '正在载入已忽略会话...' : '正在隐藏已忽略会话...');
        try {
          await loadInbox();
        } catch (error) {
          state.showIgnored = previousShowIgnored;
          state.activeWorkspaceFilter = previousFilter;
          setWorkspaceMessage(error.message || '更新忽略列表失败，请稍后再试。');
          renderWorkspace();
        } finally {
          toggleIgnoredBtn.disabled = false;
        }
      });
      searchInputEl.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          submitWorkspaceSearch().catch((error) => {
            setWorkspaceMessage(error.message || '搜索收件箱失败，请稍后再试。');
          });
        }
      });

      refreshInboxBtn.addEventListener('click', async () => {
        try {
          await loadInbox({ withRefresh: true });
        } catch (error) {
          refreshInboxBtn.disabled = false;
          setWorkspaceMessage(error.message || '刷新收件箱失败，请稍后再试。');
        }
      });
      clearBatchSelectionBtn.addEventListener('click', () => {
        clearBatchSelection();
        renderWorkspace();
      });
      syncSourceList.addEventListener('click', (event) => {
        const trigger = event.target.closest('[data-sync-source]');
        if (!trigger) {
          return;
        }
        const key = String(trigger.dataset.syncSource || '');
        if (!['include_vscode', 'include_windsurf'].includes(key)) {
          return;
        }

        const nextState = {
          ...state.syncOptions,
          [key]: !state.syncOptions[key]
        };
        if (!nextState.include_vscode && !nextState.include_windsurf) {
          setWorkspaceMessage('至少保留一个同步来源。');
          return;
        }
        state.syncOptions = nextState;
        persistSyncSourcePreference();
        renderSyncState();
      });
      batchQuickSaveBtn.addEventListener('click', () => {
        runBatchAction('quick_save').catch((error) => {
          setWorkspaceMessage(error.message || '批量存草稿失败，请稍后再试。');
        });
      });
      batchConfirmBtn.addEventListener('click', openBatchConfirmModal);
      batchReadyBtn.addEventListener('click', () => {
        runBatchAction('ready').catch((error) => {
          setWorkspaceMessage(error.message || '批量恢复待办失败，请稍后再试。');
        });
      });
      batchLaterBtn.addEventListener('click', () => {
        runBatchAction('later').catch((error) => {
          setWorkspaceMessage(error.message || '批量稍后处理失败，请稍后再试。');
        });
      });
      batchIgnoreBtn.addEventListener('click', () => {
        runBatchAction('ignored').catch((error) => {
          setWorkspaceMessage(error.message || '批量忽略失败，请稍后再试。');
        });
      });
      syncIdeBtn.addEventListener('click', () => {
        runIdeSync({ silent: false }).catch((error) => {
          setWorkspaceMessage(error.message || '同步 IDE 对话失败，请稍后再试。');
        });
      });
      autoSyncToggleBtn.addEventListener('click', () => {
        autoSyncEnabled = !autoSyncEnabled;
        persistAutoSyncPreference();
        renderSyncState();
        startAutoSyncTimer();
        setWorkspaceMessage(autoSyncEnabled ? '已开启自动同步，页面停留期间会定时补拉 IDE 对话。' : '已关闭自动同步。');
        if (autoSyncEnabled) {
          runIdeSync({ silent: true }).catch(() => {
            // Background sync failures are shown in the sync card.
          });
        }
      });

      async function handleSessionAction(event) {
        const selectToggle = event.target.closest('.session-select-toggle');
        if (selectToggle) {
          toggleSessionSelection(selectToggle.dataset.source, selectToggle.dataset.sessionId);
          renderWorkspace();
          return;
        }

        const recordButton = event.target.closest('.open-session-record');
        if (recordButton) {
          loadSessionRecord(recordButton.dataset.source, recordButton.dataset.sessionId, recordButton.dataset.title);
          return;
        }

        const sessionButton = event.target.closest('.open-session-note');
        if (sessionButton) {
          openComposerForSession(sessionButton.dataset.source, sessionButton.dataset.sessionId, sessionButton.dataset.title);
          return;
        }

        const confirmButton = event.target.closest('.open-inbox-confirm');
        if (confirmButton) {
          openConfirmModal(confirmButton.dataset.source, confirmButton.dataset.sessionId);
          return;
        }

        const quickSaveButton = event.target.closest('.quick-save-session-note');
        if (quickSaveButton) {
          quickSaveButton.disabled = true;
          quickSaveButton.textContent = '正在存草稿...';
          try {
            const resp = await fetch('/api/notes/quick-save/session', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                source: quickSaveButton.dataset.source,
                session_id: quickSaveButton.dataset.sessionId
              })
            });

            if (!resp.ok) {
              throw new Error(`保存失败: ${resp.status}`);
            }

            await loadInbox();
            setWorkspaceMessage('已经直接存成草稿，继续处理下一条就好。');
          } catch (error) {
            quickSaveButton.disabled = false;
            quickSaveButton.textContent = '一键存草稿';
            setWorkspaceMessage(error.message || '快速保存失败，请稍后再试。');
          }
          return;
        }

        const laterButton = event.target.closest('.mark-inbox-later');
        if (laterButton) {
          await fetch('/api/inbox/defer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              source: laterButton.dataset.source,
              session_id: laterButton.dataset.sessionId
            })
          });
          await loadInbox();
          setWorkspaceMessage('会话已移到“稍后处理”。');
          return;
        }

        const readyButton = event.target.closest('.mark-inbox-ready');
        if (readyButton) {
          await fetch('/api/inbox/ready', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              source: readyButton.dataset.source,
              session_id: readyButton.dataset.sessionId
            })
          });
          await loadInbox();
          setWorkspaceMessage('会话已恢复到待处理列表。');
          return;
        }

        const ignoreButton = event.target.closest('.mark-inbox-ignore');
        if (ignoreButton) {
          await fetch('/api/inbox/ignore', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              source: ignoreButton.dataset.source,
              session_id: ignoreButton.dataset.sessionId
            })
          });
          await loadInbox();
          setWorkspaceMessage('会话已被忽略，不再出现在默认收件箱里。');
        }
      }

      browserResultsEl.addEventListener('click', handleSessionAction);
      focusListEl.addEventListener('click', handleSessionAction);

      document.getElementById('closeConfirmBtn').addEventListener('click', closeConfirmModal);
      document.querySelector('[data-close-confirm]').addEventListener('click', closeConfirmModal);
      document.getElementById('closeBatchConfirmBtn').addEventListener('click', closeBatchConfirmModal);
      document.querySelector('[data-close-batch-confirm]').addEventListener('click', closeBatchConfirmModal);
      confirmForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!state.activeConfirmSession) {
          return;
        }

        setConfirmNotice('正在保存确认...');
        const payload = {
          source: state.activeConfirmSession.source,
          session_id: state.activeConfirmSession.session_id,
          title: confirmTitle.value.trim(),
          tags: parseTagInput(confirmTags.value),
          priority: confirmPriority.value
        };

        try {
          const resp = await fetch('/api/inbox/confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });

          if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            throw new Error(data?.detail || `保存失败: ${resp.status}`);
          }

          setConfirmNotice('确认已保存。', 'success');
          await loadInbox();
          window.setTimeout(closeConfirmModal, 180);
        } catch (error) {
          setConfirmNotice(error.message || '保存确认失败，请稍后再试。', 'error');
        }
      });
      batchConfirmForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const items = selectedItems();
        if (!items.length) {
          closeBatchConfirmModal();
          renderWorkspace();
          return;
        }

        setBatchConfirmNotice('正在应用批量确认...');
        try {
          const resp = await fetch('/api/inbox/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              action: 'confirm',
              priority: batchConfirmPriority.value,
              tags: parseTagInput(batchConfirmTags.value),
              items: items.map((item) => ({ source: item.source, session_id: item.session_id }))
            })
          });
          if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            throw new Error(data?.detail || `保存失败: ${resp.status}`);
          }

          setBatchConfirmNotice('批量确认已保存。', 'success');
          clearBatchSelection();
          await loadInbox();
          window.setTimeout(closeBatchConfirmModal, 180);
          setWorkspaceMessage(`已批量确认 ${items.length} 条会话。`);
        } catch (error) {
          setBatchConfirmNotice(error.message || '批量确认失败，请稍后再试。', 'error');
        }
      });

      document.getElementById('closeComposerBtn').addEventListener('click', requestCloseComposer);
      document.querySelector('[data-close-composer]').addEventListener('click', requestCloseComposer);
      document.getElementById('closeRecordBtn').addEventListener('click', closeRecordShell);
      document.querySelector('[data-close-record]').addEventListener('click', closeRecordShell);
      recordSearchInput.addEventListener('input', (event) => {
        state.recordSearch = event.target.value;
        applyRecordFilters();
      });
      recordSearchResetBtn.addEventListener('click', () => {
        recordSearchInput.value = '';
        state.recordSearch = '';
        applyRecordFilters();
      });
      document.querySelectorAll('.record-role-filter').forEach((button) => {
        button.addEventListener('click', () => {
          state.recordRole = button.dataset.role;
          applyRecordFilters();
        });
      });
      recordKeyToggleBtn.addEventListener('click', () => {
        state.recordKeyOnly = !state.recordKeyOnly;
        applyRecordFilters();
      });
      recordComposeFilteredBtn.addEventListener('click', () => {
        const messageIds = state.activeRecordFilteredMessages.map((item) => item.id);
        if (!messageIds.length) {
          return;
        }
        closeRecordShell();
        openComposerForMessages(
          messageIds,
          `来源：${state.activeRecordSession?.source || ''} · 当前筛选结果 · ${messageIds.length} 条消息`
        );
      });
      recordComposeBtn.addEventListener('click', () => {
        if (!state.activeRecordSession) return;
        closeRecordShell();
        openComposerForSession(
          state.activeRecordSession.source,
          state.activeRecordSession.session_id,
          state.activeRecordSession.title
        );
      });
      regenDraftBtn.addEventListener('click', () => generateDraft({ preserveExisting: false }));
      noteForm.addEventListener('input', persistComposerDraft);
      noteForm.addEventListener('change', persistComposerDraft);
      noteRecommendationList.addEventListener('click', (event) => {
        const trigger = event.target.closest('.pick-recommended-note');
        if (!trigger) {
          return;
        }
        noteSaveMode.value = 'append';
        existingNoteSelect.value = String(trigger.dataset.noteId || '');
        updateSaveModeUi();
        persistComposerDraft();
        setNotice('已切换为追加到推荐笔记，保存后会直接并入这篇内容。', 'success');
      });
      noteSaveMode.addEventListener('change', () => {
        if (noteSaveMode.value === 'append' && !existingNoteSelect.value && state.noteOptions.length) {
          existingNoteSelect.value = String(state.noteOptions[0].id);
        }
        updateSaveModeUi();
        persistComposerDraft();
      });
      existingNoteSelect.addEventListener('change', persistComposerDraft);

      noteForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!state.activeMessageIds.length) {
          setNotice('当前没有可保存的来源消息，请先生成草稿。', 'error');
          return;
        }
        if (noteSaveMode.value === 'append' && !existingNoteSelect.value) {
          setNotice('请选择一篇要追加的已有笔记。', 'error');
          return;
        }

        setBusy(true);
        setNotice('正在保存笔记...');

        try {
          const appendMode = noteSaveMode.value === 'append';
          const payload = {
            title: noteTitle.value.trim(),
            tags: parseTagInput(noteTags.value),
            problem: noteProblem.value.trim(),
            root_cause: noteRootCause.value.trim(),
            solution: noteSolution.value.trim(),
            key_takeaways: noteTakeaways.value.trim(),
            message_ids: state.activeMessageIds,
            existing_note_id: appendMode ? Number(existingNoteSelect.value) : null,
            status: 'draft',
            source_type: state.activeDraftMode === 'session' ? 'session' : 'mixed'
          };
          const resp = await fetch('/api/notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });

          if (!resp.ok) {
            throw new Error(`保存失败: ${resp.status}`);
          }

          const data = await resp.json();
          const noteId = Number(data?.note?.id || 0);
          if (appendMode) {
            persistAppendSummary(noteId, data?.append_summary || null);
          }
          clearComposerDraft();

          setNotice(appendMode ? '内容已追加到已有笔记，正在跳转。' : '笔记已保存，正在跳转到笔记库。', 'success');
          window.setTimeout(() => {
            window.location.href = noteId
              ? `/notes?note_id=${encodeURIComponent(noteId)}`
              : '/notes';
          }, 500);
        } catch (error) {
          setNotice(error.message || '保存失败，请稍后再试。', 'error');
        } finally {
          setBusy(false);
        }
      });

      loadWorkspacePreferences();
      loadAutoSyncPreference();
      loadSyncSourcePreference();
      renderWorkspace();
      renderSyncState();
      openComposerFromQueryIfNeeded();
      if (state.syncState?.running) {
        scheduleSyncStatusPolling({ silent: true });
      }
      if (state.showIgnored || state.workspaceQuery) {
        setWorkspaceMessage(state.workspaceQuery ? '正在搜索收件箱...' : '正在载入已忽略会话...');
        loadInbox().catch((error) => {
          setWorkspaceMessage(error.message || '加载收件箱失败，请稍后再试。');
        });
      }
      startAutoSyncTimer();
      if (autoSyncEnabled && !state.syncState?.running) {
        runIdeSync({ silent: true }).catch(() => {
          // Background sync failures are shown in the sync card.
        });
      }
      window.addEventListener('beforeunload', (event) => {
        stopSyncStatusPolling();
        if (!shouldWarnBeforeClosingComposer()) {
          return;
        }
        event.preventDefault();
        event.returnValue = '';
      });
})();
