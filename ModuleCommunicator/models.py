# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models

# Create your models here.
from rest_framework import exceptions
from ModuleCommunicator.tasks import communicator
from ModuleCommunicator.utils import filename
from ModuleManager.models import *
import ast


class ImageModel(models.Model):
    image = models.ImageField(upload_to=filename.uploaded_date)
    token = models.AutoField(primary_key=True)
    uploaded_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    modules = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        super(ImageModel, self).save(*args, **kwargs)

        module_set = self.get_module()
        module_result = list()

        for module in module_set.all():
            module_result.append(self.results.create(module=module))

        for result in module_result:
            result.get_result()
        super(ImageModel, self).save()

    # Get ModuleModel item from self.modules
    def get_module(self):
        if len(self.modules) == 0:
            return ModuleModel.objects.all()

        module_group_list = self.modules.split(',')
        module_set = None

        for module_group in module_group_list:
            try:
                modules_in_group = ModuleGroupModel.objects.get(name=module_group.strip())
            except:
                raise exceptions.ValidationError('Module not found. Please check and send again.')

            if module_set is None:
                module_set = modules_in_group.modules.all()
            else:
                module_set = module_set | modules_in_group.modules.all()

        return module_set


class ResultModel(models.Model):
    image = models.ForeignKey(ImageModel, related_name='results', on_delete=models.CASCADE)
    module = models.ForeignKey(ModuleModel)

    def save(self, *args, **kwargs):
        super(ResultModel, self).save(*args, **kwargs)
        self.set_task()
        super(ResultModel, self).save()

    # Celery Delay
    def set_task(self):
        self.task = None
        try:
            self.task = communicator.delay(url=self.module.url, image_path=self.image.image.path)
        except:
            raise exceptions.ValidationError("Module Error. Please contact the administrator")

    # Celery Get
    def get_result(self):
        try:
            task_get = ast.literal_eval(self.task.get())
            for result in task_get:
                self.module_result.create(values=result)
        except:
            raise exceptions.ValidationError("Module Error. Please contact the administrator")

    def get_module_name(self):
        return self.module.name


class ResultDetailModel(models.Model):
    result_model = models.ForeignKey(ResultModel, related_name='module_result', on_delete=models.CASCADE)
    values = models.TextField()

    def save(self, *args, **kwargs):
        if not (isinstance(self.values[0], list) and isinstance(self.values[1], dict)):
            raise exceptions.ValidationError("Module return value Error. Please contact the administrator")
        super(ResultDetailModel, self).save(*args, **kwargs)
        x, y, w, h = self.values[0]
        ResultDetailPositionModel.objects.create(result_detail_model=self, x=x, y=y, w=w, h=h)
        for item in self.values[1].items():
            self.label.create(description=item[0], score=float(item[1]))
        super(ResultDetailModel, self).save()


class ResultDetailPositionModel(models.Model):
    result_detail_model = models.OneToOneField(ResultDetailModel, related_name='position', on_delete=models.CASCADE)
    x = models.FloatField(null=True, unique=False)
    y = models.FloatField(null=True, unique=False)
    w = models.FloatField(null=True, unique=False)
    h = models.FloatField(null=True, unique=False)

    class Meta:
        ordering = ['x', 'y', 'w', 'h']


class ResultDetailLabelModel(models.Model):
    result_detail_model = models.ForeignKey(ResultDetailModel, related_name='label', on_delete=models.CASCADE)
    description = models.TextField(null=True, unique=False)
    score = models.FloatField(null=True, unique=False)

    class Meta:
        ordering = ['-score']
