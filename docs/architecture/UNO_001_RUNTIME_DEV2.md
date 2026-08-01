# UNO-001 runtime candidate 0.3.0.dev2

Windows LibreOffice подтвердил, что ручная обработка после ввода непригодна: Calc успевает преобразовать `+1`, `0708` и другие токены до запуска макроса.

Версия 0.3.0.dev2 добавляет отдельный `shift_helper_auto.py` с макросами:

- `enable_automatic_input`;
- `disable_automatic_input`;
- `automatic_input_status`.

После включения selection listener заранее переводит пустые ячейки выбранного столбца `B`, `C`, `I` или `J` и 256 строк ниже в текстовый формат. Modify listener после подтверждения ввода применяет Shift-Helper quick-input core и записывает числовую дату/время. Нормализация добавляется как hidden undo action.

Кандидат требует реальной проверки Windows/LibreOffice и не может быть слит до неё.
