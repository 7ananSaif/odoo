# -*- coding: utf-8 -*-

from collections import defaultdict
from datetime import datetime, timezone, timedelta
from lxml.builder import E
from pytz import utc

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import _, unique, OrderedSet


class Base(models.AbstractModel):
    _inherit = 'base'

    _start_name = 'date_start'       # start field to use for default gantt view
    _stop_name = 'date_stop'         # stop field to use for default gantt view

    # action_gantt_reschedule utils
    _WEB_GANTT_RESCHEDULE_FORWARD = 'forward'
    _WEB_GANTT_RESCHEDULE_BACKWARD = 'backward'
    _WEB_GANTT_RESCHEDULE_MAINTAIN_BUFFER = 'maintainBuffer'
    _WEB_GANTT_RESCHEDULE_CONSUME_BUFFER = 'consumeBuffer'
    _WEB_GANTT_LOOP_ERROR = 'loop_error'

    @api.model
    def _get_default_gantt_view(self):
        """ Generates a default gantt view by trying to infer
        time-based fields from a number of pre-set attribute names

        :returns: a gantt view
        :rtype: etree._Element
        """
        view = E.gantt(string=self._description)

        gantt_field_names = {
            '_start_name': ['date_start', 'start_date', 'x_date_start', 'x_start_date'],
            '_stop_name': ['date_stop', 'stop_date', 'date_end', 'end_date', 'x_date_stop', 'x_stop_date', 'x_date_end', 'x_end_date'],
        }
        for name in gantt_field_names.keys():
            if getattr(self, name) not in self._fields:
                for dt in gantt_field_names[name]:
                    if dt in self._fields:
                        setattr(self, name, dt)
                        break
                else:
                    raise UserError(_("Insufficient fields for Gantt View!"))
        view.set('date_start', self._start_name)
        view.set('date_stop', self._stop_name)

        return view

    @api.model
    def get_gantt_data(self, domain, groupby, read_specification, limit=None, offset=0, unavailability_fields=None, progress_bar_fields=None, start_date=None, stop_date=None, scale=None):
        """
        Returns the result of a web_read_group (and optionally search for and read records inside each
        group), and the total number of groups matching the search domain.

        :param domain: search domain
        :param groupby: list of field to group on (see ``groupby``` param of ``_read_group``)
        :param read_specification: web_read specification to read records within the groups
        :param limit: see ``limit`` param of ``_read_group``
        :param offset: see ``offset`` param of ``_read_group``
        :param boolean unavailability_fields:
        :param string start_date: start datetime in utc, e.g. "2024-06-22 23:00:00"
        :param string stop_date: stop datetime in utc
        :param string scale: among "day", "week", "month" and "year"
        :return:
            example::

                {
                    'groups': [
                        {
                            '<groupby_1>': <value_groupby_1>,
                            ...,
                            '__record_ids': [<ids>]
                        }
                    ],
                    'records': [<record data>]
                    'length': total number of groups
                    'unavailabilities': {
                        '<unavailability_fields_1>': <value_unavailability_fields_1>,
                        ...
                    }
                    'progress_bars': {
                        '<progress_bar_fields_1>': <value_progress_bar_fields_1>,
                        ...
                    }
                }
        """
        if groupby:
            # Because there is no limit by group, we can fetch record_ids as aggregate
            groups, length = self.with_context(read_group_expand=True)._formatted_read_group_with_length(
                domain, groupby, ['id:array_agg'],
                offset=offset, limit=limit,
            )

            final_result = {
                'groups': groups,
                'length': length,
            }

            all_record_ids = tuple(unique(
                record_id
                for one_group in groups
                for record_id in one_group['id:array_agg']
            ))

            # Do search_fetch to order records (model order can be no-trivial)
            all_records = self.with_context(active_test=False).search_fetch([('id', 'in', all_record_ids)], read_specification.keys())
        else:
            # Not groupby => search records directly and create one group to respect the API
            all_records = self.search_fetch(domain, read_specification.keys())
            final_result = {
                'groups': [{
                    'id:array_agg': all_records._ids,
                    '__extra_domain': [],
                }],
                'length': 1,
            }

        final_result['records'] = all_records.with_env(self.env).web_read(read_specification)

        if unavailability_fields is None:
            unavailability_fields = []
        if progress_bar_fields is None:
            progress_bar_fields = []

        ordered_set_ids = OrderedSet(all_records._ids)
        res_ids_for_unavailabilities = defaultdict(set)
        res_ids_for_progress_bars = defaultdict(set)
        for group in final_result['groups']:
            for field in unavailability_fields:
                res_id = group[field][0] if group[field] else False
                if res_id:
                    res_ids_for_unavailabilities[field].add(res_id)
            for field in progress_bar_fields:
                res_id = group[field][0] if group[field] else False
                if res_id:
                    res_ids_for_progress_bars[field].add(res_id)
            # Reorder __record_ids
            group['__record_ids'] = list(ordered_set_ids & OrderedSet(group.pop('id:array_agg')))
            # We don't need these in the gantt view
            del group['__extra_domain']
            group.pop('__fold', None)

        if unavailability_fields or progress_bar_fields:
            start, stop = fields.Datetime.from_string(start_date), fields.Datetime.from_string(stop_date)

        unavailabilities = {}
        for field in unavailability_fields:
            unavailabilities[field] = self._gantt_unavailability(field, list(res_ids_for_unavailabilities[field]), start, stop, scale)
        final_result['unavailabilities'] = unavailabilities

        progress_bars = {}
        for field in progress_bar_fields:
            progress_bars[field] = self._gantt_progress_bar(field, list(res_ids_for_progress_bars[field]), start, stop)
        final_result['progress_bars'] = progress_bars

        return final_result

    def web_gantt_init_old_vals_per_pill_id(self, vals):
        old_vals_per_pill_id = defaultdict(dict)
        for field in vals:
            field_type = self.fields_get(field)[field]['type']
            if field_type in ['many2many', 'one2many']:
                old_vals_per_pill_id[self.id][field] = self[field].ids or False
            elif field_type == 'many2one':
                old_vals_per_pill_id[self.id][field] = self[field].id or False
            else:
                old_vals_per_pill_id[self.id][field] = self[field]

        return old_vals_per_pill_id

    @api.model
    def web_gantt_reschedule(
        self,
        vals,
        reschedule_method,
        record_id,
        dependency_field_name,
        dependency_inverted_field_name,
        start_date_field_name,
        stop_date_field_name,
    ):
        """
        Reschedule a record according to the provided parameters.

        :param vals: dict containing the new vals for the moved pill
        :param reschedule_method: The method of the rescheduling, either 'maintainBuffer' or 'consumeBuffer'.
        :param record_id: The moved record.
        :param dependency_field_name: The field name representing the relation between the master and slave records.
        :param dependency_inverted_field_name: The field name representing the relation between the slave and parent records.
        :param start_date_field_name: The start date field used in the Gantt view.
        :param stop_date_field_name: The stop date field used in the Gantt view.
        :return: A dictionary with the following structure:

            - type: Notification type.
            - message: Notification message.
            - old_vals_per_pill_id: A dictionary where the key is the pill ID, and the value is
              another dictionary containing the start and stop dates before rescheduling.

        :rtype: dict
        """

        if reschedule_method not in (self._WEB_GANTT_RESCHEDULE_CONSUME_BUFFER, self._WEB_GANTT_RESCHEDULE_MAINTAIN_BUFFER):
            raise ValueError(self.env._("Invalid reschedule method %s", reschedule_method))

        record = self.env[self._name].browse(record_id)

        message = self.env._("Tasks rescheduled")
        # if the pill is moved without changing dates, or there are no dependencies between pills, or the pill is moved to the past => only write the moved pill (like Manual rescheduling)
        if (not (start_date_field_name in vals and stop_date_field_name in vals and dependency_field_name and dependency_inverted_field_name)) or (start_date_field_name in vals and datetime.strptime(vals[start_date_field_name], '%Y-%m-%d %H:%M:%S') < datetime.now()):
            old_vals_per_pill_id = record.web_gantt_init_old_vals_per_pill_id(vals)
            record.write(vals)
            return {
                "type": "success",
                "message": message,
                "old_vals_per_pill_id": old_vals_per_pill_id,
            }

        with self.env.cr.savepoint() as sp:
            log_messages, old_vals_per_pill_id = record._web_gantt_action_reschedule_candidates(dependency_field_name, dependency_inverted_field_name, start_date_field_name, stop_date_field_name, reschedule_method, vals)
            has_errors = bool(log_messages.get("errors"))
            sp.close(rollback=has_errors)
        notification_type = "success"
        if has_errors or log_messages.get("warnings"):
            message = self._web_gantt_get_reschedule_message(log_messages)
            notification_type = "warning" if has_errors else "info"
        return {
            "type": notification_type,
            "message": message,
            "old_vals_per_pill_id": old_vals_per_pill_id,
        }

    def action_rollback_scheduling(self, old_vals_per_pill_id):
        for record in self:
            vals = old_vals_per_pill_id.get(str(record.id), old_vals_per_pill_id.get(record.id))
            if vals:
                record.write(vals)

    def gantt_undo_drag_drop(self, drag_action, data=None):
        if not self.exists():
            return False
        if drag_action == "copy":
            return self.unlink()
        elif drag_action == "reschedule" and data:
            return self.write(data)
        return False

    @api.model
    def _gantt_progress_bar(self, field: str, res_ids: list[int], start: str, stop: str):
        """ Get progress bar value per record.

            This method is meant to be overriden by each related model that want to
            implement this feature on Gantt groups. The progressbar is composed
            of a value and a max_value given for each groupedby field.

            Example::

                field = 'foo',
                res_ids = [1, 2]
                start_date = 01/01/2000, end_date = 01/07/2000,
                self = base()

            Result::

                {
                    1: {'value': 50, 'max_value': 100},
                    2: {'value': 25, 'max_value': 200},
                }

            :param field: field on which there are progressbars
            :param res_ids: res_ids of related records for which we need to compute progress bar
            :param start: start date in utc
            :param stop: end date in utc
            :returns: dict of value and max_value per record
        """
        return {}

    @api.model
    def _gantt_unavailability(self, field, res_ids, start, stop, scale):
        """ Get unavailabilities data for a given set of resources.

        This method is meant to be overriden by each model that want to
        implement this feature on a Gantt view. A subslot is considered
        unavailable (and greyed) when totally covered by an unavailability.

        Example::

            >>> _gantt_unavailability(
            ...    field="employee_id",
            ...    res_ids=[3, 9],
            ...    start='01/01/2000'  # UTC,
            ...    stop='01/07/2000'  # UTC,
            ...    scale='week',
            ... )
            {
                value: [{
                    start: <start date of first unavailabity in UTC format>,
                    stop: <stop date of first unavailabity in UTC format>
                }, {
                    start: <start date of second unavailabity in UTC format>,
                    stop: <stop date of second unavailabity in UTC format>
                }, ...]
                ...
            }

        For example Marcel (3) is unavailable January 2 afternoon and
        January 4 the whole day, the dict should look like this::

            {
                3: [{
                    'start': '2018-01-02 14:00:00',
                    'stop': '2018-01-02 18:00:00'
                }, {
                    'start': '2018-01-04 08:00:00',
                    'stop': '2018-01-04 18:00:00'
                }]
            }

        Note that John (9) has no unavailabilies and thus 9 is not in
        returned dict

        :param string field: name of a many2X field
        :param list res_ids: list of values for field for which we want unavailabilities (a value is either False or an id)
        :param datetime start: start datetime
        :param datetime stop: stop datetime
        :param string scale: among "day", "week", "month" and "year"
        :returns: dict of unavailabilities
        """
        return {}

    def _web_gantt_get_reschedule_message_per_key(self, key, params=None):
        if key == self._WEB_GANTT_LOOP_ERROR:
            return _("The dependencies are not valid, there is a cycle.")
        elif key == "past_error":
            if params:  # params is the record that is in the past
                return _("%s cannot be scheduled in the past", params.display_name)
            else:
                return _("Impossible to schedule in the past.")
        else:
            return ""

    def _web_gantt_get_reschedule_message(self, log_messages):
        def get_messages(logs):
            messages = []
            for key in logs:
                message = self._web_gantt_get_reschedule_message_per_key(key, log_messages.get(key))
                if message:
                    messages.append(message)
            return messages

        messages = []
        errors = log_messages.get("errors")
        if errors:
            messages = get_messages(log_messages.get("errors"))
        else:
            messages = get_messages(log_messages.get("warnings", []))
        return "\n".join(messages)

    def _web_gantt_get_direction(self, start_date_field_name, vals):
        date_start = datetime.strptime(vals[start_date_field_name], '%Y-%m-%d %H:%M:%S')
        return self._WEB_GANTT_RESCHEDULE_FORWARD if date_start > self[start_date_field_name] else self._WEB_GANTT_RESCHEDULE_BACKWARD

    def _web_gantt_action_reschedule_candidates(
        self,
        dependency_field_name, dependency_inverted_field_name,
        start_date_field_name, stop_date_field_name,
        reschedule_method,
        vals
    ):
        """ Prepare the candidates according to the provided parameters and move them.

            :param dependency_field_name: The field name of the relation between the pill and its parents.
            :param dependency_inverted_field_name: The field name of the relation between the pill and its children.
            :param start_date_field_name: The start date field used in the gantt view.
            :param stop_date_field_name: The stop date field used in the gantt view.
            :param reschedule_method: The method of the rescheduling 'maintainBuffer' or 'consumBuffer'
            :param vals: dict containing the new vals for the moved pill
            :return: tuple(valid, message) (valid = True if Successful, message = None or contains the notification text if
                    text if valid = True or the error text if valid = False.
        """

        search_forward = self._web_gantt_get_direction(start_date_field_name, vals) == self._WEB_GANTT_RESCHEDULE_FORWARD
        candidates_ids = []
        if self._web_gantt_check_cycle_existance_and_get_rescheduling_candidates(
            candidates_ids, dependency_inverted_field_name if search_forward else dependency_field_name,
            start_date_field_name, stop_date_field_name,
        ):
            return {'errors': self._WEB_GANTT_LOOP_ERROR}, {}

        return self._web_gantt_move_candidates(
            start_date_field_name, stop_date_field_name,
            dependency_field_name, dependency_inverted_field_name,
            search_forward, candidates_ids,
            reschedule_method == self._WEB_GANTT_RESCHEDULE_CONSUME_BUFFER, vals
        )

    def _web_gantt_is_candidate_in_conflict(self, start_date_field_name, stop_date_field_name, dependency_field_name, dependency_inverted_field_name):
        return (
            any(r[start_date_field_name] and r[stop_date_field_name] and self[start_date_field_name] < r[stop_date_field_name] for r in self[dependency_field_name])
            or any(r[start_date_field_name] and r[stop_date_field_name] and self[stop_date_field_name] > r[start_date_field_name] for r in self[dependency_inverted_field_name])
        )

    def _web_gantt_update_next_pills_first_possible_date(self,
        dependency_field_name,
        dependency_inverted_field_name,
        search_forward,
        first_possible_start_date_per_candidate,
        last_possible_end_date_per_candidate,
        consume_buffer,
        start_date_field_name,
        stop_date_field_name,
        start_date,
        end_date,
        old_start_date,
        old_end_date
    ):
        for next in self[dependency_inverted_field_name if search_forward else dependency_field_name]:
            if search_forward:
                end_date = end_date.astimezone(utc)
                first_possible_start_date_per_candidate[next.id] = max(first_possible_start_date_per_candidate.get(next.id, end_date), end_date)
                if not consume_buffer and next[start_date_field_name] > old_end_date:
                    buffer_duration = (next[start_date_field_name] - old_end_date).total_seconds()
                    start_date_after_buffer = end_date + timedelta(seconds=buffer_duration)
                    first_possible_start_date_per_candidate[next.id] = max(first_possible_start_date_per_candidate.get(next.id, start_date_after_buffer), start_date_after_buffer)
            else:
                start_date = start_date.astimezone(utc)
                last_possible_end_date_per_candidate[next.id] = min(last_possible_end_date_per_candidate.get(next.id, start_date), start_date)
                if not consume_buffer and next[stop_date_field_name] < old_start_date:
                    buffer_duration = (old_start_date - next[stop_date_field_name]).total_seconds()
                    end_date_after_buffer = start_date - timedelta(seconds=buffer_duration)
                    last_possible_end_date_per_candidate[next.id] = min(last_possible_end_date_per_candidate.get(next.id, end_date_after_buffer), end_date_after_buffer)

    def _web_gantt_get_first_and_last_possible_dates(self, dependency_field_name, dependency_inverted_field_name, search_forward, stop_date_field_name, start_date_field_name):
        first_possible_start_date_per_candidate = {}
        last_possible_end_date_per_candidate = {}

        for candidate in self:
            related_candidates = (candidate[dependency_field_name] if search_forward else candidate[dependency_inverted_field_name]).filtered(lambda pill: pill[start_date_field_name] and pill[stop_date_field_name])
            not_replanned_candidates = related_candidates - self

            if not not_replanned_candidates:
                continue

            boundary_date = stop_date_field_name if search_forward else start_date_field_name
            boundary_dates = not_replanned_candidates.mapped(boundary_date)

            if search_forward:
                first_possible_start_date_per_candidate[candidate.id] = max(boundary_dates).astimezone(utc)
            else:
                last_possible_end_date_per_candidate[candidate.id] = min(boundary_dates).astimezone(utc)

        return first_possible_start_date_per_candidate, last_possible_end_date_per_candidate

    def _web_gantt_move_candidates(self, start_date_field_name, stop_date_field_name, dependency_field_name, dependency_inverted_field_name, search_forward, candidates_ids, consume_buffer, vals):
        """ Move candidates according to the provided parameters.

            :param start_date_field_name: The start date field used in the gantt view.
            :param stop_date_field_name: The stop date field used in the gantt view.
            :param dependency_field_name: The field name of the relation between the pill and pills blocked by it.
            :param dependency_inverted_field_name: The field name of the relation between the pill and pills blocking it.
            :param search_forward: True if the direction = 'forward'
            :param candidates_ids: The candidates to reschedule
            :param consume_buffer: True if reschedule_method = 'consumeBuffer' else False
            :param vals: dict containing the new vals for the moved pill
            :return: dict of list containing 2 keys, errors and warnings
        """
        result = {
            "errors": [],
            "warnings": [],
        }

        old_vals_per_pill_id = self.web_gantt_init_old_vals_per_pill_id(vals)

        candidates = self.browse([id for id in candidates_ids if id != self.id])
        self.write(vals)
        first_possible_start_date_per_candidate, last_possible_end_date_per_candidate = candidates._web_gantt_get_first_and_last_possible_dates(dependency_field_name, dependency_inverted_field_name, search_forward, stop_date_field_name, start_date_field_name)

        self._web_gantt_update_next_pills_first_possible_date(dependency_field_name, dependency_inverted_field_name, search_forward, first_possible_start_date_per_candidate, last_possible_end_date_per_candidate, consume_buffer, start_date_field_name,
            stop_date_field_name, self[start_date_field_name], self[stop_date_field_name], old_vals_per_pill_id[self.id][start_date_field_name], old_vals_per_pill_id[self.id][stop_date_field_name],
        )

        for candidate in candidates:
            if consume_buffer and not candidate._web_gantt_is_candidate_in_conflict(start_date_field_name, stop_date_field_name, dependency_field_name, dependency_inverted_field_name):
                continue

            start_date, end_date = candidate._web_gantt_reschedule_compute_dates(
                (first_possible_start_date_per_candidate if search_forward else last_possible_end_date_per_candidate)[candidate.id],
                search_forward,
                start_date_field_name, stop_date_field_name
            )
            start_date, end_date = start_date.astimezone(timezone.utc), end_date.astimezone(timezone.utc)
            old_start_date, old_end_date = candidate[start_date_field_name], candidate[stop_date_field_name]
            if not candidate._web_gantt_reschedule_write_new_dates(
                start_date, end_date,
                start_date_field_name, stop_date_field_name
            ):
                result["errors"].append("past_error")
                result["past_error"] = candidate
                return result, {}

            old_vals_per_pill_id[candidate.id] = {
                start_date_field_name: old_start_date,
                stop_date_field_name: old_end_date,
            }

            candidate._web_gantt_update_next_pills_first_possible_date(dependency_field_name, dependency_inverted_field_name, search_forward, first_possible_start_date_per_candidate, last_possible_end_date_per_candidate, consume_buffer, start_date_field_name,
                stop_date_field_name, candidate[start_date_field_name], candidate[stop_date_field_name], old_start_date, old_end_date,
            )

        return result, old_vals_per_pill_id

    def _web_gantt_record_has_dependencies(self):
        return True

    def _web_gantt_check_cycle_existance_and_get_rescheduling_candidates(self,
        candidates_ids, dependency_field_name,
        start_date_field_name, stop_date_field_name,
        visited=None, ancestors=None,
    ):
        """ Get the current records' related records rescheduling candidates

            :param candidates_ids: empty list that will contain the candidates at the end
            :param dependency_field_name: The field name of the relation between the pill and candidates
                (pills blocked by the pill if move forward or blocking the pill if move backward)
            :param start_date_field_name: The start date field used in the gantt view.
            :param stop_date_field_name: The stop date field used in the gantt view.
            :param visited: set containing all the visited pills
            :param ancestors: set containing the visited ancestors for the current pill
            :return: bool, True if there is a cycle, else False.
                candidates_id will also contain the pills to plan in a valid topological order
        """
        if visited is None:
            visited = set()
        if ancestors is None:
            ancestors = []
        visited.add(self.id)
        ancestors.append(self.id)

        for child in (self[dependency_field_name] if self._web_gantt_record_has_dependencies() else []):
            if child.id in ancestors:
                return True

            if child.id not in visited and child._web_gantt_reschedule_is_record_candidate(start_date_field_name, stop_date_field_name) and child._web_gantt_check_cycle_existance_and_get_rescheduling_candidates(candidates_ids, dependency_field_name, start_date_field_name, stop_date_field_name, visited, ancestors):
                return True

        ancestors.pop()
        candidates_ids.insert(0, self.id)

        return False

    def _web_gantt_reschedule_compute_dates(
        self, date_candidate, search_forward, start_date_field_name, stop_date_field_name
    ):
        """ Compute start_date and end_date according to the provided arguments.
            This method is meant to be overridden when we need to add constraints that have to be taken into account
            in the computing of the start_date and end_date.

            :param date_candidate: The optimal date, which does not take any constraint into account.
            :param start_date_field_name: The start date field used in the gantt view.
            :param stop_date_field_name: The stop date field used in the gantt view.
            :return: a tuple of (start_date, end_date)
            :rtype: tuple(datetime, datetime)
        """
        search_factor = (1 if search_forward else -1)
        duration = search_factor * (self[stop_date_field_name] - self[start_date_field_name])
        return sorted([date_candidate, date_candidate + duration])

    def _web_gantt_reschedule_is_record_candidate(self, start_date_field_name, stop_date_field_name):
        """ Get whether the record is a candidate for the rescheduling. This method is meant to be overridden when
            we need to add a constraint in order to prevent some records to be rescheduled. This method focuses on the
            record itself

            :param start_date_field_name: The start date field used in the gantt view.
            :param stop_date_field_name: The stop date field used in the gantt view.
            :return: True if record can be rescheduled, False if not.
            :rtype: bool
        """
        return self._web_gantt_reschedule_can_record_be_rescheduled(start_date_field_name, stop_date_field_name)

    def _web_gantt_reschedule_can_record_be_rescheduled(self, start_date_field_name, stop_date_field_name):
        self.ensure_one()
        return self[start_date_field_name] and self[stop_date_field_name] \
            and self[start_date_field_name].replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)

    def _web_gantt_reschedule_write_new_dates(
        self, new_start_date, new_stop_date, start_date_field_name, stop_date_field_name
    ):
        """ Write the dates values if new_start_date is in the future.

            :param new_start_date: The start_date to write.
            :param new_stop_date: The stop_date to write.
            :param start_date_field_name: The start date field used in the gantt view.
            :param stop_date_field_name: The stop date field used in the gantt view.
            :return: True if successful, False if not.
            :rtype: bool

            epsilon = 30 seconds was added because the first valid interval can be now and because of some seconds, it will become < now() at the comparaison moment
            it's a matter of some seconds
        """
        new_start_date = new_start_date.astimezone(timezone.utc).replace(tzinfo=None)
        if new_start_date < datetime.now() + timedelta(seconds=-30):
            return False

        self.write({
            start_date_field_name: new_start_date,
            stop_date_field_name: new_stop_date.astimezone(timezone.utc).replace(tzinfo=None)
        })
        return True
