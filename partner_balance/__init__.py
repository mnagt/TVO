# -*- coding: utf-8 -*-

from . import controllers
from . import models
from . import services


def post_init_hook(env):
    configs = env['partner.balance.user.config'].search([])
    configs._sync_group()
