class annotation(db.Model):
    __tablename__ = 'annotation'

    sampleid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    survey_code = db.Column(db.String(10), nullable=False)
    answer_dict = db.Column(db.String(500))
    annotator = db.Column(db.String(100))

    def __init__(survey_code, answer_dict=None, annotator=None):
        self.survey_code = survey_code
        self.answer_dict = answer_dict
        self.annotator = annotator

