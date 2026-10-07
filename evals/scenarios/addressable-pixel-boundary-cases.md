# Addressable-pixel review boundary cases

Synthetic human pairs, scoped to the actual requirement/model. They do not establish automatic detector efficacy or change electrical guarantees.

| Supported claim | Contrasting case | Review distinction |
|---|---|---|
| A fitted capacitor has explicit nominal capacitance and controlled minimum specification. | The source supplies only CAPACITOR/0402, and the PCB value is empty. | Presence and connection do not provide a reproducible value. Do not replace the missing value with a typical application figure or call the component absent. |
| The selected part revision explicitly removes the need for external bypass components. | An earlier or unidentified revision only has a capacitor in its applicable circuit. | A successor can support a new design; its component-free provision cannot retroactively close an old source's missing value. |
| A matched software version and CPU branch produces pulses inside the applicable device's bounds. | The same source pulses exceed a different generation's interval. | Record source cycles, conditions, and waveform/host limits; a library name alone does not certify every device revision. Do not infer an actual historical unit failure from an unmatched later table. |
| DOUT is connected to three parallel ports. | Three downstream pixels are connected successively DOUT→DIN. | Parallel branches receive the same remaining stream; serial pixels successively consume separate 24-bit words. Do not assign serial addressing behavior to a branched net. |
| A timing guarantee is specified with a 15pF load. | Three connected inputs each specified with a maximum 15pF permit a worst-case input sum of 45pF, plus cable loading. | A maximum is not an actual or minimum capacitance. Do not carry the single-load guarantee across the full permitted larger load; verify a designated fanout/cable condition without inferring a measured overload or condemning every parallel header. |
| An author requires a resistor in the external controller→DIN path. | A rail short or externally energized DOUT bypasses that resistor. | Preserve the actual path and condition. Absence on a bare board does not prove the external provision was omitted; that resistor does not protect all paths. |
| A device's own electrical table extends above its absolute supply maximum. | A complete, consistent working range and absolute boundary are established. | Preserve the contradiction and query or constrain the guarantee; never treat the broad table condition or absolute ratings alone as permission to operate there. |
| The supplier's four-terminal map and two-page source include the actual schematic and PCB view. | A page produces no extracted text, or a library namespace says opto. | Inspect original pixels and actual model/pins. Neither an empty text extraction nor a broad library category proves the page blank or device an optocoupler. |

Retain real material and version gaps. No fixed universal capacitor, GPIO voltage, pixel current, cable length, fanout count or reset interval is added by these pairs.
