# jcode-django

Django URL routing, ORM relations and signal edges for [jcode](https://github.com/codewithjoes-tech/jcode).

## What it does

Detects three Django patterns and emits typed edges in the jcode graph — so blast radius queries show the full impact of changing a view, model, or signal sender.

| Pattern | Edge emitted |
|---------|-------------|
| `path('url/', view_fn)` / `re_path(...)` | `route`: url module → view function |
| `ForeignKey(Model)` / `OneToOneField` / `ManyToManyField` | `references`: model → related model |
| `@receiver(post_save, sender=Model)` | `signal`: handler → sender model |

## Install

```bash
jcode add django
```

Or manually:

```bash
pip install jcode-django
```

## How it works

Once installed, jcode auto-detects this plugin on any repo that has `django` in its `requirements.txt` or `pyproject.toml`. No configuration needed.

```python
# URL routing — jcode sees this:
urlpatterns = [
    path('posts/', views.post_list),
]
# emits: url module --[route]--> post_list

# ORM relation — jcode sees this:
class Post(models.Model):
    author = ForeignKey(User, on_delete=CASCADE)
# emits: Post --[references]--> User

# Signal — jcode sees this:
@receiver(post_save, sender=User)
def on_user_saved(sender, **kwargs): ...
# emits: on_user_saved --[signal]--> User
```

## Part of the jcode ecosystem

- [jcode](https://github.com/codewithjoes-tech/jcode) — core CLI and MCP server
- [jcode-registry](https://github.com/codewithjoes-tech/jcode-registry) — plugin registry

---

Made by [Joel Thomas](https://codewithjoe.in)
