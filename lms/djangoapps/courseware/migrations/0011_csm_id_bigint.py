# -*- coding: utf-8 -*-
# Generated by Django 1.11.23 on 2019-08-28 15:50


import lms.djangoapps.courseware.fields

from django.conf import settings
from django.db import migrations
from django.db.migrations import AlterField

class CsmBigInt(AlterField):
	'''
	Subclass AlterField migration class to split SQL between two different databases
	We can't use the normal AlterField migration operation because Django generate and routes migrations at the model
	level and the coursewarehistoryextended_studentmodulehistoryextended table is in a different database
	'''
	def database_forwards(self, app_label, schema_editor, from_state, to_state):
		if hasattr(schema_editor.connection, 'is_in_memory_db') and schema_editor.connection.is_in_memory_db():
			# sqlite3 doesn't support 'MODIFY', so skipping during tests
			return
		to_model = to_state.apps.get_model(app_label, self.model_name)
		if schema_editor.connection.alias == 'student_module_history':
			if settings.FEATURES["ENABLE_CSMH_EXTENDED"]:
				
				if schema_editor.connection.vendor == 'postgresql':

					schema_editor.execute("ALTER TABLE coursewarehistoryextended_studentmodulehistoryextended ALTER COLUMN student_module_id TYPE bigint SET NOT NULL;")
					
				else:
					schema_editor.execute("ALTER TABLE coursewarehistoryextended_studentmodulehistoryextended MODIFY student_module_id bigint UNSIGNED NOT NULL;")

		elif self.allow_migrate_model(schema_editor.connection.alias, to_model):
			if schema_editor.connection.vendor == 'postgresql':
				schema_editor.execute("ALTER TABLE courseware_studentmodule ALTER COLUMN id ADD GENERATED ALWAYS;")
			else:
				schema_editor.execute("ALTER TABLE courseware_studentmodule MODIFY id bigint UNSIGNED AUTO_INCREMENT NOT NULL;")

	def database_backwards(self, app_label, schema_editor, from_state, to_state):
		# Make backwards migration a no-op, app will still work if column is wider than expected
		pass

class Migration(migrations.Migration):

	dependencies = [
		('courseware', '0010_auto_20190709_1559'),
		('coursewarehistoryextended', '0002_force_studentmodule_index'),
	]

	operations = [
		CsmBigInt(
			model_name='studentmodule',
			name='id',
			field=lms.djangoapps.courseware.fields.UnsignedBigIntAutoField(primary_key=True, serialize=False),
		)
	]
