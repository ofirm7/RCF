-- Prevent duplicate permits per property and duplicate refund cases per permit.

ALTER TABLE permits
    ADD CONSTRAINT uq_permits_property_number UNIQUE (property_id, permit_number);

ALTER TABLE refund_cases
    ADD CONSTRAINT uq_refund_cases_permit UNIQUE (permit_id);
