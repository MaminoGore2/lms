import logging
import re
from typing import Dict, Any, Union
from datetime import datetime

logger = logging.getLogger(__name__)


class RulesEngine:
    """
    Интерпретатор правил для условий сертификации и других бизнес-логик.
    Поддерживает: and, or, not, сравнения (>=, <=, >, <, ==, !=)
    """

    @staticmethod
    def evaluate(expression: str, context: Dict[str, Any]) -> bool:
        """
        Вычисляет логическое выражение с подстановкой значений из контекста.

        Пример:
            expression: "completed_all and avg_score >= 80"
            context: {"completed_all": True, "avg_score": 85}
            Результат: True
        """
        try:
            # Безопасное вычисление выражений
            # Заменяем названия переменных на их значения из контекста
            expr = expression

            # Сначала заменяем строковые значения (в кавычках)
            def replace_strings(match):
                return match.group(0)  # оставляем как есть

            # Затем заменяем переменные (идентификаторы) на их значения
            for var_name, var_value in context.items():
                if isinstance(var_value, (int, float)):
                    expr = re.sub(rf'\b{var_name}\b', str(var_value), expr)
                elif isinstance(var_value, bool):
                    expr = re.sub(rf'\b{var_name}\b', str(var_value), expr)
                elif isinstance(var_value, str):
                    expr = re.sub(rf'\b{var_name}\b', f"'{var_value}'", expr)

            # Заменяем логические функции
            expr = expr.replace('and(', '')  # упрощенная обработка

            # Используем встроенную eval с ограниченным globals
            allowed_names = {
                'True': True, 'False': False,
                'and': lambda x, y: x and y,
                'or': lambda x, y: x or y,
                'not': lambda x: not x
            }

            # Простой парсинг для учебных целей
            # В продакшене лучше использовать ast.literal_eval или специализированные библиотеки
            result = eval(expr, {"__builtins__": {}}, allowed_names)
            return bool(result)

        except Exception as e:
            logger.error(f"Rule evaluation failed for expression '{expression}': {e}")
            return False

    @staticmethod
    def check_certificate_eligibility(course_config: Dict, user_progress: Dict) -> bool:
        """
        Проверяет, может ли пользователь получить сертификат.
        """
        rule = course_config.get('certificate_rule', {}).get('expression')
        if not rule:
            # Если правило не задано, считаем что курс пройден
            return user_progress.get('completed_all', False)

        # Подготавливаем контекст
        context = {
            'completed_all': user_progress.get('completed_all', False),
            'completed_all_lessons': user_progress.get('completed_all_lessons', False),
            'avg_score': user_progress.get('average_score', 0),
            'final_exam_score': user_progress.get('final_exam_score', 0),
            'total_attempts': user_progress.get('total_attempts', 1),
            'days_enrolled': user_progress.get('days_enrolled', 0)
        }

        return RulesEngine.evaluate(rule, context)

    @staticmethod
    def calculate_test_score(answers: Dict[str, List[str]], test_snapshot: Dict) -> float:
        """
        Вычисляет балл за тест на основе конфигурации и ответов.
        """
        questions = test_snapshot.get('questions', [])
        total_points = 0
        earned_points = 0

        for question in questions:
            q_id = question['question_id']
            q_points = question.get('points', 1.0)
            total_points += q_points

            correct = question.get('correct_answers', [])
            user_answer = answers.get(q_id, [])

            # Приводим к списку для единообразия
            if not isinstance(user_answer, list):
                user_answer = [user_answer]

            if question['type'] == 'single_choice':
                # Для single choice - строгое совпадение
                if user_answer == correct:
                    earned_points += q_points
            elif question['type'] == 'multiple_choice':
                # Для multiple choice - все правильные и нет лишних
                if set(user_answer) == set(correct):
                    earned_points += q_points
                else:
                    # Частичное совпадение
                    correct_set = set(correct)
                    user_set = set(user_answer)
                    if user_set.issubset(correct_set) and user_set:
                        # Частичный балл
                        earned_points += q_points * (len(user_set) / len(correct_set))
            else:
                # Текстовые вопросы - простая проверка
                if user_answer and user_answer[0].strip().lower() in [c.lower() for c in correct]:
                    earned_points += q_points

        if total_points == 0:
            return 0.0

        score_percentage = (earned_points / total_points) * 100
        return round(score_percentage, 2)