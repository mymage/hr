# Copyright 2020 Stefano Consolaro (Ass. PNLUG - Gruppo Odoo <http://odoo.pnlug.it>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models, api, _
import datetime
import json
import logging

_logger = logging.getLogger(__name__)


class ServiceAllocate(models.Model):
    """
    Allocated service with definition of all the template components
    """

    # model
    _name = 'service.allocate'
    _description = 'Allocate service'

    # fields
    # template service reference
    service_template_id = fields.Many2one('service.template',
                                          string='Template service',
                                          required=True,
                                          )
    # off duty service
    off_duty = fields.Boolean('Off Duty',
                              related='service_template_id.off_duty')

    # container service reference
    service_container_id = fields.Many2one('service.container',
                                           string='Container service',
                                           required=True,
                                           )
    # generation id (eg. to select a list of aumatic generated services)
    generation_id = fields.Char('Generation ID',
                                help='Group services generated automatically')
    # dedicated color
    service_color = fields.Char('Color',
                                related='service_template_id.base_color')

    # assigned vehicles
    vehicle_ids = fields.Many2many('fleet.vehicle', string='Vehicles')
    # message for vehicles check
    vehicle_check = fields.Text('Vehicles coverage', store=True)
    # assigned employee
    employee_ids = fields.Many2many('hr.employee', string='Team')
    # employee names
    employee_names = fields.Text('Employees', compute='_compute_emply_name', store=True)
    # message for skills check
    employee_check = fields.Text('Skills coverage', store=True)
    # assigned equipment
    equipment_ids = fields.Many2many('maintenance.equipment', string='Equipment')
    # message for equipments check
    equipment_check = fields.Text('Equipments coverage', store=True)

    # locality reference
    locality = fields.Char('Locality')

    # scheduled start time
    scheduled_start = fields.Datetime('Start scheduled', required=True)
    # scheduled start time
    scheduled_stop = fields.Datetime('Stop scheduled',
                                     compute='_compute_scheduled_stop', store=True)
    # effective start time
    start_real = fields.Datetime('Start real')
    # effective stop time
    stop_real = fields.Datetime('Stop real')

    # state of the service
    state = fields.Selection([('planned', 'Planned'),
                              ('confirmed', 'Confirmed'),
                              ('closed', 'Closed')
                              ], string='State', required=True, default='planned')

    # parent service that generate this as next service
    parent_service_id = fields.Many2one('service.allocate',
                                        'Parent Service',
                                        help='Service that generated this one by \
                                              template next option'
                                        )
    # next service generate from this one
    next_service_id = fields.Many2one('service.allocate',
                                      'Next Service',
                                      help='Service generated by this one by \
                                            template next option'
                                      )

    # define record name to display in form view
    _rec_name = 'id'

    @api.depends('scheduled_start')
    def _compute_scheduled_stop(self):
        for service in self:
            if service.scheduled_start:
                slot = service.service_template_id.duration
                # avoid empty value of duration
                slot = slot if slot > 0 else 1
                service.scheduled_stop = (service.scheduled_start +
                                          datetime.timedelta(hours=slot))

        return

    # main changes monitor methods
    @api.multi
    @api.onchange('employee_ids')
    def _employee_ids_change(self):
        """
        Call methods on employees changes
        """
        self._compute_emply_name()
        self._check_skill_request()

    @api.multi
    @api.onchange('equipment_ids')
    def _equipment_ids_change(self):
        """
        Call methods on equipments changes
        """
        self._check_equipment_request()

    @api.multi
    @api.onchange('vehicle_ids')
    def _vehicle_ids_change(self):
        """
        Call methods on vehicles changes
        """
        self._check_vehicle_request()

    # changes dedicated methods
    def _compute_emply_name(self):
        """
        Update field with name list
        """
        for service in self:
            service.employee_names = ''
            for employee in service.employee_ids:
                service.employee_names += employee.name + '\n'
        return

    def _check_skill_request(self):
        """
        Check if all required skills are covered by employees
        """
        for service in self:
            # clear error message
            self.employee_check = ''
            # get requested skills by template
            skill_request = service.service_template_id.exp_skill_ids
            # for each request counts available employees
            for request in skill_request:
                available_qty = 0
                # chek requested skill in each employee
                for employee in service.employee_ids:
                    if self.env['hr.employee.skill'].search(
                        [('employee_id', '=', employee.id),
                         ('skill_id', '=', request.skill_id.id),
                         ]):
                        available_qty += 1
                if available_qty < request.min_qty:
                    self.employee_check += (_('Missing %s\n')
                                            % (request.skill_id.name))
                if request.max_qty > 0 and available_qty > request.max_qty:
                    self.employee_check += (_('Too many %s\n')
                                            % (request.skill_id.name))
        if self.employee_check == '':
            self.employee_check = 'All covered'
        return

    def _check_equipment_request(self):
        """
        Check if all required categories are covered by equipments
        """
        for service in self:
            # clear error message
            self.equipment_check = ''
            # get requested categoryies by template
            category_request = service.service_template_id.exp_eqp_cat_ids
            # for each request counts available categories
            for request in category_request:
                available_qty = 0
                # chek requested categories in each equipment
                for equipment in service.equipment_ids:
                    if self.env['maintenance.equipment'].search(
                        [('id', '=', equipment.id),
                         ('category_id', '=', request.eqp_cat_id.id),
                         ]):
                        available_qty += 1
                if available_qty < request.min_qty:
                    self.equipment_check += (_('Missing %s\n')
                                             % (request.eqp_cat_id.name))
                if request.max_qty > 0 and available_qty > request.max_qty:
                    self.equipment_check += (_('Too many %s\n')
                                             % (request.eqp_cat_id.name))
        if self.equipment_check == '':
            self.equipment_check = 'All covered'
        return

    def _check_vehicle_request(self):
        """
        Check if all required type are covered by vehicles
        """
        for service in self:
            # clear error message
            self.vehicle_check = ''
            # get requested categoryies by template
            vehicle_request = service.service_template_id.exp_vehicle_ids
            # for each request counts available types
            for request in vehicle_request:
                available_qty = 0
                # chek requested types in each vehicle
                for vehicle in service.vehicle_ids:
                    if self.env['fleet.vehicle'].search(
                        [('id', '=', vehicle.id),
                         ('vehicle_category_id', '=', request.vehicle_category_id.id),
                         ]):
                        available_qty += 1
                if available_qty < request.min_qty:
                    self.vehicle_check += (_('Missing %s\n')
                                           % (request.vehicle_category_id.name))
                if request.max_qty > 0 and available_qty > request.max_qty:
                    self.vehicle_check += (_('Too many %s\n')
                                           % (request.vehicle_category_id.name))
        if self.vehicle_check == '':
            self.vehicle_check = 'All covered'
        return

    # utility to filter container services to template's container services
    @api.onchange('service_template_id')
    def _get_template_container(self):
        """
        Extract list of container services associated to the template service
        """
        container_services = []
        # reset value to avoid errors
        self.service_container_id = [(5)]
        for glob_srv in self.service_template_id.service_container_ids:
            container_services.append(glob_srv.id)

        return {'domain': {'service_container_id': [('id', 'in', container_services)]}}

    def double_assign(self, parameters):
        """
        _TODO_ _FIX_ direct call to service.rule.double_assign on the button
        """
        result = self.env['service.rule'].double_assign(parameters['resource_type'],
                                                        parameters['srv_id'])
        return result

    def rule_call(self, parameters):
        """
        _TODO_ _FIX_ direct call to service.rule.rule_call on the button
        """
        result = self.env['service.rule'].rule_call(parameters['rule_name'],
                                                    parameters['srv_id'])
        return result

    def check_resource_rule(self, parameters):
        """
        Check rules for each resource associated to the service
        @param srv_id int: id of the service
        """

        # get employee of the service
        for employee in self.env['service.allocate'] \
                            .search([('id', '=', parameters['srv_id'])]).employee_ids:
            # memorixe a dictionary of rules and fields
            rule_method = {}
            # get rules of the profile associated to the employee
            for rule in employee.profile_id.parameter_ids:
                # create rule element if not exists
                try:
                    rule_method[rule.rule_id.method]
                except:
                    rule_method[rule.rule_id.method] = {}
                # save rile/field value
                rule_method[rule.rule_id.method][rule.rule_field_id.field_name] = \
                    rule.field_value
            _logger.info(employee.name+' '+json.dumps(rule_method))
            # print(employee.name+' '+json.dumps(rule_method))
        return

    @api.model
    def create(self, values):
        """
        Override create function to manage next service generation
        """
        new_service = super(ServiceAllocate, self).create(values)

        # generation id can be set by the automatic flow
        if not new_service.generation_id:
            new_service.generation_id = datetime.datetime.now(). \
                strftime("M %Y-%m-%d-%H-%M-%S")

        # generate next service if present on template
        if new_service.service_template_id.next_template_id.id:
            # get end of the original service
            next_strt = new_service.scheduled_stop
            # get next service template
            next_serv = new_service.service_template_id.next_template_id.id
            # get first container of the next service template
            next_cont = new_service.service_template_id.service_container_ids[0].id

            new_service_data = {
                "service_template_id"   : next_serv,
                "service_container_id"  : next_cont,
                "scheduled_start"       : next_strt,
                "parent_service_id"     : new_service.id,
                "generation_id"         : new_service.generation_id,
                }
            new_service_nxt = super(ServiceAllocate, self).create(new_service_data)
            # save child reference
            new_service.next_service_id = new_service_nxt

        return new_service

    @api.multi
    def write(self, values):
        """
        Override with check elements for double assigns before save
        """
        ServiceAllocate_write = super(ServiceAllocate, self).write(values)
        # call double assignment
        self.double_assign({'resource_type': 'all', 'srv_id': self.id})

        return ServiceAllocate_write

    @api.multi
    def unlink(self):
        """
        Override with unlink for next services
        """
        # scan services for next element
        for service in self:
            # when next service is defined and not yet present in self list
            if service.next_service_id.id and service.next_service_id not in self:
                service.next_service_id.unlink()

        return super(ServiceAllocate, self).unlink()
