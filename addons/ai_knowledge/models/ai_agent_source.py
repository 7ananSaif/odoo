from odoo import _, api, fields, models

from odoo.addons.ai.utils.html_extractor import HTMLExtractor


class AIAgentSource(models.Model):
    _name = 'ai.agent.source'
    _inherit = ['ai.agent.source']

    article_id = fields.Many2one('knowledge.article', string="Source Article")
    type = fields.Selection(
        selection_add=[('knowledge_article', 'Knowledge Article')],
        ondelete={'knowledge_article': lambda recs: recs.write({'type': 'binary'})}
    )

    @api.model
    def create_from_articles(self, article_ids, agent_id):
        """Create AI agent sources from articles."""
        vals_list = []
        articles = self.env['knowledge.article'].browse(article_ids)
        for article in articles:
            vals_list.append({
                'name': article.name,
                'agent_id': agent_id,
                'article_id': article.id,
                'url': article.article_url,
                'type': 'knowledge_article',
            })
        sources = super().create(vals_list)
        if sources:
            self.env.ref('ai.ir_cron_process_sources')._trigger()

    @api.depends_context('uid')
    @api.depends('article_id')
    def _compute_user_has_access(self):
        """
        Override to check if the user has access to the article.
        """
        article_sources = self.filtered(lambda s: s.type == 'knowledge_article')
        for source in article_sources:
            # evaluate access with the current user without elevating to sudo (used in LLM response flow)
            source.user_has_access = source.article_id.with_user(self.env.user).user_can_read
        super(AIAgentSource, self - article_sources)._compute_user_has_access()

    def _update_name(self):
        """
        Override to update the name of the source if it is a knowledge article.
        """
        if not self:
            return

        source = self[0]

        if source.type != 'knowledge_article':
            return super()._update_name()

        current_name = source.article_id.name
        if source.name != current_name:
            source.name = current_name

    def action_access_source(self):
        """Override to open the article if article_id exists"""
        self.ensure_one()
        if self.url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.url,
                'target': 'new',
            }
        return super().action_access_source()

    def _get_sources_to_process(self):
        """
        Override to append the knowledge article sources to process.
        :return: sources to process
        :rtype: ai.agent.source recordset
        """
        sources_to_process = super()._get_sources_to_process()
        target_articles = self.env['ai.agent.source'].search([
            ('type', '=', 'knowledge_article'),
            ('status', '=', 'processing'),
        ]).mapped('article_id')
        knowledge_sources_to_process = self.env['ai.agent.source'].search([
            ('article_id', 'in', target_articles.ids),
        ])
        return sources_to_process | knowledge_sources_to_process

    def _fetch_content(self, source):
        """
        Override to fetch the content of a knowledge article source
        and all its descendants if the source is a knowledge article.
        :param source: source to fetch the content from
        :type source: ai.agent.source record
        :return: dictionary with 'content', 'title', and 'error' keys, or None
        :rtype: dict or None
        """
        if source.type != 'knowledge_article':
            return super()._fetch_content(source)

        extractor = HTMLExtractor()
        parent_article = source.article_id
        article_descendants = parent_article._get_descendants()
        all_articles = article_descendants | parent_article
        content = ""
        for article in all_articles:
            result = extractor.extract_from_html(article.body)
            if result and result['content']:
                content += result['content'] + '\n'
            else:
                return {"content": None, "error": result.get('error', _("Failed to extract content from the articles."))}
        return {"content": content, "error": None}
