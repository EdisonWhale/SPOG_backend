import pydantic
from app.models.project.ProjectCreate import ProjectCreate

# email validator carried over (and rescoped, dropping author target)?
try:
    ProjectCreate.model_validate({
        'name': 'Claims Insights', 'purpose': 'AI claims',
        'businessOwner': 'Jane Smith', 'businessOwnerEmail': 'not-an-email',
        'productOwner': 'John Doe', 'productOwnerEmail': 'john@highmark.com',
        'technicalOwner': 'Alex Lee', 'technicalOwnerEmail': 'alex@highmark.com',
        'vpSponsor': 'Pat Jones', 'vpSponsorEmail': 'pat@highmark.com',
    })
    print('email validator enforced: FALSE (BAD)')
except pydantic.ValidationError as e:
    print('email validator enforced:', 'Invalid email format' in str(e))

print('validators on ProjectCreate:', list(ProjectCreate.__pydantic_decorators__.field_validators.keys()))
print('author excluded:', 'author' not in ProjectCreate.model_fields)

# happy path still works
ok = ProjectCreate.model_validate({
    'name': 'Claims Insights', 'purpose': 'AI claims',
    'businessOwner': 'Jane Smith', 'businessOwnerEmail': 'jane@highmark.com',
    'productOwner': 'John Doe', 'productOwnerEmail': 'john@highmark.com',
    'technicalOwner': 'Alex Lee', 'technicalOwnerEmail': 'alex@highmark.com',
    'vpSponsor': 'Pat Jones', 'vpSponsorEmail': 'pat@highmark.com',
})
print('happy path name:', ok.name)
