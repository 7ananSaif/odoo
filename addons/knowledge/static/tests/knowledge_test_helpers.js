import { mailModels } from "@mail/../tests/mail_test_helpers";
import { defineModels, mockService, onRpc } from "@web/../tests/web_test_helpers";
import { KnowledgeArticle } from "./mock_server/mock_models/knowledge_article";
import { KnowledgeArticleThread } from "./mock_server/mock_models/knowledge_article_thread";
import { beforeEach, expect } from "@odoo/hoot";

export function defineKnowledgeModels() {
    return defineModels(knowledgeModels);
}

export function mockKnowledgeCommentsService() {
    mockService("knowledge.comments", {
        createThread() {},
        createThreadAndPost() {},
        createVirtualThread() {},
        deleteThread() {},
        fetchMessages() {},
        getCommentsState: () => ({
            articleId: undefined,
            activeThreadId: undefined,
            shouldOpenActiveThread: false,
            threadRecords: {},
            threads: {},
            disabledEditorThreads: {},
            editorThreads: {},
            displayMode: "handler",
            focusedThreads: new Set(),
            deletedThreadIds: new Set(),
            hasFocus: () => false,
        }),
        loadRecords() {},
        loadThreads() {},
        setArticleId() {},
        updateResolveState() {},
    });
}

export function mockKnowledgePermissionPanelRpc() {
    return beforeEach(() => {
        onRpc("knowledge.article", "remove_member", ({ args }) => {
            const [article_id, member_id] = args;
            expect.step(`remove member ${member_id} on article ${article_id}`);
        });
        onRpc("knowledge.article", "set_internal_permission", ({ args }) => {
            const [article_id, permission] = args;
            expect.step(`change permission to ${permission} on article ${article_id}`);
        });
        onRpc("knowledge.article", "set_is_article_visible_by_everyone", ({ args }) => {
            const [article_id, is_visible_by_everyone] = args;
            expect.step(`change visibility to ${is_visible_by_everyone ? "everyone" : "members"} on article ${article_id}`);
        });
        onRpc("knowledge.article", "set_member_permission", ({ args }) => {
            const [article_id, member_id, permission] = args;
            expect.step(`change permission of member ${member_id} to ${permission} on article ${article_id}`);
        });
        onRpc("knowledge.article", "restore_article_access", ({ args }) => {
            const [article_id] = args;
            expect.step(`restoring access on article ${article_id}`);
        });
    });
}

export const knowledgeModels = { ...mailModels, KnowledgeArticle, KnowledgeArticleThread };
