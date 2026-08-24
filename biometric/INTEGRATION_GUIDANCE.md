# Registration integration guidance

PaddleOCR output is assistance, not identity truth. `scan_ic` returns only local
unconfirmed candidates: `full_name`, normalized `ic`, and
`requires_confirmation=true`. A human must confirm them. Only trusted orchestration
may later map the confirmed name to `citizen_display_name`; the document IC must
never become opaque backend `citizen_id`.

The authorized flow remains:

`consent -> document capture -> OCR candidates -> human confirmation -> live camera -> frozen biometric mother -> protected template storage/linkage -> separate backend PIN creation`

The document portrait is never an SFace enrolment reference. OCR does not create
`template_id`, `audit_event_id`, or `verification_completed_at`; it never reads a
PIN and does not emit a canonical OCR status. OCR completion is not
`ENROLMENT_COMPLETED`.

`MATCH_CONFIRMED` still does not authorize. FastAPI/trusted backend orchestration
must require the later correct PIN in the same valid session before
`AUTHORIZATION_GRANTED`.
