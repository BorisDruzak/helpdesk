from work_with_word_docs import WordDocumentHandler

def test_list_files():
    handler = WordDocumentHandler('files/')
    files = handler.list_files()
    assert isinstance(files, list), "Метод list_files должен возвращать список."
    assert all(file.endswith('.doc') or file.endswith('.docx') for file in files), \
        "Все элементы списка должны быть файлами .doc или .docx."

def test_extract_text():
    handler = WordDocumentHandler('files/')
    sample_file = 'example.docx'  # Убедитесь, что этот файл существует в папке files/
    text = handler.extract_text(sample_file)
    assert isinstance(text, str), "Метод extract_text должен возвращать строку."
    assert len(text) > 0, "Документ должен содержать некоторый текст."
    print(isinstance(text, str))
    print(len(text) > 0)
def test_prepare_preview():
    handler = WordDocumentHandler('files/')
    sample_file = 'example.docx'
    title, preview = handler.prepare_preview(sample_file)
    print(title, preview)
    assert isinstance(title, str) and isinstance(preview, str), \
        "Метод prepare_preview должен возвращать кортеж из двух строк."
    assert len(preview) <= 203, "Предварительный просмотр не должен превышать 200 символов плюс три точки."
    print(len(preview) <= 203)
if __name__ == "__main__":
    test_list_files()
    test_extract_text()
    test_prepare_preview()
    print("Все тесты пройдены успешно!")