# Physical dataset and evaluation

Capture representative normal and defective leather pieces under documented front, back and directional lighting conditions. Use a physical piece ID, lot ID, view, lighting, operator and capture time. Record labels independently with experienced inspectors when available and annotate visible defect locations and severity. Record uncertain labels separately.

Split by physical piece before training or augmentation. Keep all photos of the same piece together and consider grouping by lot and imaging session when they could leak appearance across splits. Hold out a representative test split before tuning. Store private photos locally; Git ignores the raw, annotation and processed directories. The project does not include any approved physical dataset today.
