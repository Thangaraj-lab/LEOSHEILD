# Business rules currently enforced

- AI recommendation and raw AI JSON are immutable evidence. Human decisions are stored in a separate table.
- Pass and Grade require a completed latest inspection, complete coverage, acceptable image quality, and a non-empty human reason. Grade requires a grade label.
- Hold and Reject can be recorded for incomplete or failed attempts, with a reason.
- A product's latest attempt controls lot status. A prior Pass cannot carry forward after a reinspection.
- Reinspection is a new inspection record; it does not add a physical-product count.
- Operator-selected lighting labels are stored with each capture. Operator supplemental captures are labeled as not submitted to Laptop 1 and do not alter its result.
- Export readiness requires registration quantity to equal expected quantity, buyer requirements configured and profile-matched, every latest inspection completed, complete required coverage, acceptable capture quality, a latest Pass/Grade human decision, required named measurements, and reviewed accepted lab reports. At least one accepted product is required.
- Rejected products are excluded from accepted quantity. Dispatch authorization requires the owner role, a ready gate and dispatch quantity exactly equal to accepted quantity. Only one dispatch authorization is allowed per lot.
- The current app creates only an owner account. A broader role matrix is not implemented.
- No inspection mode other than real is implemented. Configuring mock mode prevents startup rather than returning demo results.
