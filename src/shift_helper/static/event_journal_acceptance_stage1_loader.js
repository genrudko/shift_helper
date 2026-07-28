"use strict";

/* Load staged acceptance repairs only after the underlying grid is stable. */
(() => {
    const root = document.getElementById("event-journal");
    if (!root) return;

    function appendStylesheet(id, source) {
        const existing = document.getElementById(id);
        if (existing) return existing;
        const link = document.createElement("link");
        link.id = id;
        link.rel = "stylesheet";
        link.href = source;
        document.head.appendChild(link);
        return link;
    }

    function appendScript(id, source) {
        return new Promise((resolve, reject) => {
            const existing = document.getElementById(id);
            if (existing) {
                resolve(existing);
                return;
            }
            const script = document.createElement("script");
            script.id = id;
            script.src = source;
            script.addEventListener("load", () => resolve(script), {once: true});
            script.addEventListener("error", reject, {once: true});
            document.body.appendChild(script);
        });
    }

    async function load() {
        if (
            root.dataset.operatorRepairReady !== "true"
            || root.dataset.videoAcceptanceRepair !== "ready"
            || typeof window.shiftHelperZoom?.apply !== "function"
        ) {
            requestAnimationFrame(load);
            return;
        }
        if (root.dataset.acceptanceStage1Loading === "true") return;
        root.dataset.acceptanceStage1Loading = "true";
        try {
            await appendScript(
                "event-journal-sheet-transform-contract-v1-js",
                "/static/event_journal_sheet_transform_contract_v1.js",
            );
            if (root.dataset.sheetTransformContract !== "ready") {
                throw new Error("Sheet transform contract did not initialize");
            }
            window.shiftHelperStage1BaseZoomApply = window.shiftHelperZoom.apply.bind(
                window.shiftHelperZoom,
            );
            await appendScript(
                "event-journal-context-fallback-v1",
                "/static/event_journal_context_fallback_v1.js",
            );
            root.dataset.contextFallbackLoaded = "true";
            appendStylesheet(
                "event-journal-acceptance-stage1-css",
                "/static/event_journal_acceptance_stage1.css",
            );
            await appendScript(
                "event-journal-acceptance-stage1-js",
                "/static/event_journal_acceptance_stage1.js",
            );
            await appendScript(
                "event-journal-acceptance-stage1-compat-js",
                "/static/event_journal_acceptance_stage1_compat.js",
            );
            await appendScript(
                "event-journal-acceptance-stage1-state-js",
                "/static/event_journal_acceptance_stage1_state.js",
            );
            root.dataset.acceptanceStage1Loaded = "true";
            await appendScript(
                "event-journal-acceptance-stage2-js",
                "/static/event_journal_acceptance_stage2.js",
            );
            root.dataset.acceptanceStage2Loaded = "true";
            appendStylesheet(
                "event-journal-acceptance-stage3-css",
                "/static/event_journal_acceptance_stage3.css",
            );
            appendStylesheet(
                "event-journal-acceptance-stage3-sticky-css",
                "/static/event_journal_acceptance_stage3_sticky.css",
            );
            await appendScript(
                "event-journal-acceptance-stage3-js",
                "/static/event_journal_acceptance_stage3.js",
            );
            await appendScript(
                "event-journal-acceptance-stage3-virtualization-js",
                "/static/event_journal_acceptance_stage3_virtualization.js",
            );
            root.dataset.acceptanceStage3Loaded = "true";
            appendStylesheet(
                "event-journal-acceptance-stage4-css",
                "/static/event_journal_acceptance_stage4.css",
            );
            await appendScript(
                "event-journal-acceptance-stage4-js",
                "/static/event_journal_acceptance_stage4.js",
            );
            await appendScript(
                "event-journal-acceptance-stage4-alignment-js",
                "/static/event_journal_acceptance_stage4_alignment_contract.js",
            );
            root.dataset.acceptanceStage4Loaded = "true";
            appendStylesheet(
                "event-journal-acceptance-stage5-css",
                "/static/event_journal_acceptance_stage5.css",
            );
            await appendScript(
                "event-journal-acceptance-stage5-js",
                "/static/event_journal_acceptance_stage5.js",
            );
            root.dataset.acceptanceStage5Loaded = "true";
            appendStylesheet(
                "event-journal-acceptance-stage6-css",
                "/static/event_journal_acceptance_stage6.css",
            );
            await appendScript(
                "event-journal-acceptance-stage6-js",
                "/static/event_journal_acceptance_stage6.js",
            );
            root.dataset.acceptanceStage6Loaded = "true";
            appendStylesheet(
                "event-journal-acceptance-stage7-css",
                "/static/event_journal_acceptance_stage7.css",
            );
            await appendScript(
                "event-journal-acceptance-stage7-js",
                "/static/event_journal_acceptance_stage7.js",
            );
            root.dataset.acceptanceStage7Loaded = "true";
        } catch (error) {
            root.dataset.acceptanceStageError = String(error);
            console.error("Acceptance repair failed to load", error);
        } finally {
            delete root.dataset.acceptanceStage1Loading;
        }
    }

    load();
})();
