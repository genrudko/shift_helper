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
        window.shiftHelperStage1BaseZoomApply = window.shiftHelperZoom.apply.bind(
            window.shiftHelperZoom,
        );
        try {
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
        } catch (error) {
            root.dataset.acceptanceStageError = String(error);
            console.error("Acceptance repair failed to load", error);
        } finally {
            delete root.dataset.acceptanceStage1Loading;
        }
    }

    load();
})();
