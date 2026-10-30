from django.db import migrations


def populate(apps, schema_editor):
    Publisher = apps.get_model("catalog", "Publisher")
    Work = apps.get_model("catalog", "Work")
    for publisher in Publisher.objects.all().iterator():
        owners = list(Work.objects.filter(publisher=publisher).values_list("owner_id", flat=True).distinct())
        for index, owner in enumerate(owners):
            if index == 0:
                target = publisher
                target.owner_id = owner
                target.save(update_fields=["owner"])
            else:
                target = Publisher.objects.create(name=publisher.name, owner_id=owner)
                Work.objects.filter(publisher=publisher, owner_id=owner).update(publisher=target)
            cities = list(Work.objects.filter(publisher=target, owner_id=owner, city__isnull=False)
                          .values_list("city_id", flat=True).distinct())
            if len(cities) == 1:
                target.default_city_id = cities[0]
                target.save(update_fields=["default_city"])


class Migration(migrations.Migration):
    dependencies = [("catalog", "0005_publisher_default_city_publisher_owner")]
    operations = [migrations.RunPython(populate, migrations.RunPython.noop)]
