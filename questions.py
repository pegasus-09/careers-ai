class Question:
    def __init__(self, question: dict):
        self.q_id = question['id']
        self.text = question['text']
        self.question_type = question['question_type']
        self.target = question['target']
        self.scale = question['scale']
