import logging
from django.apps import apps
from django.contrib.postgres import fields as pg_fields
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from .forms import DynamicForm, DummyForm
from .utils import freeze, hashsum


logger = logging.getLogger('dynamic_forms.models')


class FormManager(models.Manager):
    def get_or_create(self, form_spec):
        frozen = freeze(form_spec)
        sha1 = hashsum(frozen).hexdigest()
        obj = None

        # find if this form_spec exists already
        for possible in self.filter(sha1=sha1):
            if possible.form_spec == form_spec:
                obj = possible
                break

        # create new database object and save it
        if not obj:
            obj = self.create(form_spec=form_spec, sha1=sha1)

        # store already calculated frozen_spec
        obj.frozen_spec = frozen
        return obj


class Form(models.Model):
    objects = FormManager()

    sha1 = models.CharField(max_length=40, db_index=True)
    form_spec = pg_fields.JSONField()

    class Meta:
        abstract = apps.get_containing_app_config(__name__) is None
        ordering = ('id',)
        verbose_name = _("Form")
        verbose_name_plural = _("Forms")

    @cached_property
    def frozen_spec(self):
        return freeze(self.form_spec)

    @cached_property
    def form_class(self):
        return DynamicForm.get_form_class_by(self.form_spec, frozen=self.frozen_spec)

    @cached_property
    def form_class_or_dummy(self):
        try:
            return self.form_class
        except ValueError as error:
            logger.critical("DB has invalid form_spec with id %d: %s", self.id, error)
            return DummyForm

    def save(self, **kwargs):
        if not self.sha1:
            self.sha1 = hashsum(freeze(self.form_spec)).hexdigest()
        return super().save(**kwargs)

    def __str__(self):
        return "<Form {}, {} fields, sha1:{}>".format(self.pk, len(self.form_spec), self.sha1)
